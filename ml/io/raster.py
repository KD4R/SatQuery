"""The single validated entry point for reading a raster off disk.

Why there is exactly one
------------------------
Three review rounds of the foundation commit turned up nineteen real defects, and
the recurring shape of them was not carelessness in any one function -- it was a
guard applied to one function and not mirrored onto the next. ``confusion()``
learned to reject a label array containing ``2``; ``area_hectares`` did not, and
went on counting it as flood. ``Measurement`` learned that a geographic CRS is
unsafe; ``is_projected`` had a separate, weaker opinion. Each individual fix was
right and the set of them still leaked, because every function was defending
itself independently.

So this module is the only way a GeoTIFF becomes an array in this package. It
validates once, at the boundary, and returns an array together with the
``RasterSpec`` describing it. Everything downstream may then assume:

  * the array's shape matches the spec's width, height and band count
  * the CRS is what the spec says, read from the file rather than assumed
  * the pixel size is a positive magnitude in the units of that CRS
  * declared band order and declared scale have been *cross-checked* against the
    file's own metadata where the file carries any, and disagreement was refused
  * no-data has been normalised to ``NaN``, so ``isfinite`` is a complete test

The point is that a downstream function cannot be handed something unvalidated
without someone deliberately bypassing this module.

Declared versus inferred, refined
---------------------------------
ADR-0007 D3 says scale and band order are declared data, never inferred, because
inferring them from pixel values is sometimes wrong and a sometimes-wrong silent
conversion is worse than no conversion. That still holds: nothing here inspects
pixel values.

But file *metadata* is not inference. A GeoTIFF band description reading ``VV`` is
the producer's own statement, and Sen1Floods11 carries one on every band. So the
rule here is stronger than either declaration or metadata alone: the caller
declares, the file is read, and if the two disagree the read is refused. That is
what would have caught the band-order error in the foundation commit at the first
run rather than at review.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject

from packages.contracts import BackscatterScale, Polarization, RasterSpec
from packages.contracts.crs_policy import is_area_safe
from ml.geo.crs import utm_epsg_for


class RasterReadError(ValueError):
    """A raster could not be read, or contradicted what the caller declared."""


@dataclass(frozen=True)
class Raster:
    """A validated array, the spec describing it, and its georeferencing.

    Frozen, and the array is set read-only, so a consumer cannot quietly alter the
    pixels behind a spec that has already been checked -- the same reasoning that
    made every contract collection a tuple.

    ``transform`` lives here rather than on ``RasterSpec`` because ``RasterSpec`` is
    a contract shared with other roles and describes pixel geometry, not
    georeferencing; putting a rasterio ``Affine`` on it would drag a geospatial
    dependency into a package that must import without one. ``Raster`` is local to
    this module and has no such constraint.
    """

    data: npt.NDArray[np.float32]
    spec: RasterSpec
    transform: Affine

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) in the units of ``spec.crs``.

        Delegated to rasterio rather than multiplying the transform here, for two
        reasons that only became visible once this ran on someone else's machine.

        The first is portability. This was originally written ``transform @ (0, 0)``,
        which works on affine 3.x and raises ``TypeError`` on affine 2.x -- and
        ``requirements.txt`` pins only ``rasterio>=1.3``, so both resolve. Siddharth
        hit the crash and swapped in ``*``, which is correct and is why this code
        runs at all; but ``*`` on a point is pending deprecation in affine 3.x, so
        that trade is a crash on old versions for a removal on new ones.
        ``array_bounds`` is public rasterio API and is stable across both.

        The second is correctness, and it is the part the operator swap could not
        have caught. Taking two opposite corners describes the array only while the
        transform is north-up. Under rotation or a flip the true extent is the hull
        of all four corners, and the two-corner form silently returns a box that is
        too small -- a plausible wrong answer, which is the failure mode this module
        exists to prevent. ``array_bounds`` uses all four whenever the rotation
        terms are non-zero.

        Every Sen1Floods11 chip is north-up, so no committed number moves; the
        regression test pins both halves of that claim.
        """
        west, south, east, north = array_bounds(self.spec.height, self.spec.width, self.transform)
        return (west, south, east, north)

    def band(self, polarization: Polarization) -> npt.NDArray[np.float32]:
        """Return one band **by name**, never by index.

        Indexing by position is how the band-order defect propagates: ``data[0]``
        is correct only if the file's order matches the reader's assumption, and
        the two disagreed in the foundation commit for a week. Asking for
        ``Polarization.VV`` cannot be wrong, because the lookup goes through the
        spec that was cross-checked at read time.
        """
        try:
            index = self.spec.band_order.index(polarization)
        except ValueError:
            raise RasterReadError(
                f"raster has no {polarization.value} band; it carries "
                f"{tuple(b.value for b in self.spec.band_order)}"
            ) from None
        band: npt.NDArray[np.float32] = self.data[index]
        return band


def _polarization_from_description(description: str | None) -> Polarization | None:
    """Map a GeoTIFF band description to a Polarization, or ``None`` if unreadable.

    Deliberately strict: only an exact case-insensitive match on a known
    polarisation counts. A description of ``"band 1"`` or ``"sigma0"`` says nothing
    about polarisation and must not be forced into one, because a wrong
    cross-check is worse than no cross-check.
    """
    if not description:
        return None
    normalised = description.strip().upper()
    for polarization in Polarization:
        if normalised == polarization.value:
            return polarization
    return None


def read_raster(
    path: str | Path,
    *,
    declared_band_order: tuple[Polarization, ...],
    declared_scale: BackscatterScale,
) -> Raster:
    """Read a GeoTIFF, validate it against what the caller declared, and return both.

    Parameters
    ----------
    path
        Local filesystem path. Remote hrefs go through
        :func:`services.inference.validation.validate_href` first; this function does not
        fetch, so that the SSRF allowlist cannot be bypassed by handing it a URL.
    declared_band_order
        What the caller believes the bands are, in file order. Cross-checked
        against the file's band descriptions where it carries them.
    declared_scale
        Power, amplitude or decibel. Cannot be cross-checked -- no GeoTIFF
        convention records it -- so it is taken on the caller's word and carried
        forward explicitly rather than guessed downstream.

    Raises
    ------
    RasterReadError
        If the file cannot be opened, if the band count disagrees with
        ``declared_band_order``, if the file's own band descriptions contradict it,
        or if the file carries no CRS.
    """
    path = Path(path)
    if not path.is_file():
        raise RasterReadError(f"no such raster: {path}")

    with rasterio.open(path) as source:
        if source.count != len(declared_band_order):
            raise RasterReadError(
                f"{path.name} has {source.count} band(s) but caller declared "
                f"{len(declared_band_order)}: "
                f"{tuple(b.value for b in declared_band_order)}"
            )

        _cross_check_band_order(path, source.descriptions, declared_band_order)

        if source.crs is None:
            raise RasterReadError(
                f"{path.name} carries no CRS. Every downstream guard keys off the "
                "CRS, so a raster without one cannot be measured or reprojected -- "
                "assuming EPSG:4326 here is exactly the guess this package refuses."
            )

        data = source.read().astype(np.float32)
        nodata = source.nodata
        transform = source.transform
        crs = str(source.crs)
        height, width = source.height, source.width

    # Normalise no-data to NaN at the boundary, so that `isfinite` is a complete
    # test everywhere downstream. Review round one found validate_finite_fraction
    # reporting a raster of -9999 as 100% valid precisely because a finite sentinel
    # had been allowed to travel past the reader.
    if nodata is not None and math.isfinite(nodata):
        data = np.where(data == np.float32(nodata), np.float32("nan"), data)

    spec = RasterSpec(
        band_order=declared_band_order,
        scale=declared_scale,
        dtype="float32",
        crs=crs,
        width=width,
        height=height,
        # abs(): a north-up GeoTIFF has a negative y step, which is a direction,
        # not a size. RasterSpec rejects a non-positive pixel size for this reason.
        pixel_size_m=(abs(transform.a), abs(transform.e)),
        # Already folded into NaN above, so the spec records that state rather than
        # the original sentinel -- the array and its description must not disagree.
        nodata=None,
    )

    data.setflags(write=False)
    return Raster(data=data, spec=spec, transform=transform)


def _cross_check_band_order(
    path: Path,
    descriptions: tuple[str | None, ...],
    declared: tuple[Polarization, ...],
) -> None:
    """Refuse when the file's own band descriptions contradict the declaration.

    This is the check that would have caught the foundation commit's band-order
    error on its first run. The documentation said VH-then-VV; every Sen1Floods11
    file says ``('VV', 'VH')``. Nothing crashed, because nothing compared them.
    """
    from_file = tuple(_polarization_from_description(d) for d in descriptions)
    if all(entry is None for entry in from_file):
        # No usable descriptions. The declaration stands unverified, which is the
        # documented fallback rather than a failure -- plenty of valid products
        # carry no band names.
        return

    for index, (declared_band, file_band) in enumerate(zip(declared, from_file)):
        if file_band is not None and file_band is not declared_band:
            raise RasterReadError(
                f"{path.name} band {index} is described as {file_band.value} but the "
                f"caller declared {declared_band.value}. Declared order "
                f"{tuple(b.value for b in declared)}, file order "
                f"{tuple(b.value if b else '?' for b in from_file)}. "
                "Reading them mismatched would normalise each channel with the "
                "other channel's statistics and produce a plausible wrong answer, "
                "so this is refused rather than reconciled."
            )


def reproject_to_area_safe_crs(raster: Raster, *, target_crs: str | None = None) -> Raster:
    """Reproject onto a CRS in which area may legitimately be measured.

    Sen1Floods11 chips are stored in EPSG:4326 at 8.983e-05 degrees, which reads
    like a 10 m grid and is not one: a degree of longitude is 111 km at the equator
    and 78 km at 45 degrees, so pixel area in square metres varies with latitude.
    Measuring before reprojecting is the single most common defect in this domain,
    and the guards in :mod:`ml.geo.area` refuse it -- this is the function that
    makes the refusal actionable rather than merely correct.

    Parameters
    ----------
    target_crs
        Explicit target, or ``None`` to select the UTM zone containing the
        raster's centre. Automatic selection is the default because a hardcoded
        zone is wrong for most of India -- Guntur is 44N and the Brahmaputra is
        46N, while a single constant of 43N is right only for Kerala.

    Returns
    -------
    Raster
        A new raster. The input is unchanged.
    """
    if is_area_safe(raster.spec.crs) and target_crs is None:
        return raster

    with rasterio.Env():
        source_crs = rasterio.crs.CRS.from_string(raster.spec.crs)

        if target_crs is None:
            target_crs = _utm_for_raster(raster)

        transform, width, height = calculate_default_transform(
            source_crs,
            target_crs,
            raster.spec.width,
            raster.spec.height,
            *raster.bounds,
        )

        destination = np.full(
            (raster.data.shape[0], height, width), np.float32("nan"), dtype=np.float32
        )
        for index in range(raster.data.shape[0]):
            reproject(
                source=raster.data[index],
                destination=destination[index],
                src_transform=raster.transform,
                src_crs=source_crs,
                dst_transform=transform,
                dst_crs=target_crs,
                # Bilinear, not nearest: backscatter in dB is a continuous
                # quantity, and nearest-neighbour would preserve speckle spikes
                # that the threshold then reads as real. Masks are a different
                # case and must be reprojected with nearest -- they are not
                # reprojected here at all, because the mask is derived *after*
                # this step precisely to avoid that question.
                resampling=Resampling.bilinear,
                src_nodata=np.float32("nan"),
                dst_nodata=np.float32("nan"),
            )

    spec = RasterSpec(
        band_order=raster.spec.band_order,
        scale=raster.spec.scale,
        dtype="float32",
        crs=str(target_crs),
        width=width,
        height=height,
        pixel_size_m=(abs(transform.a), abs(transform.e)),
        nodata=None,
    )
    destination.setflags(write=False)
    return Raster(data=destination, spec=spec, transform=transform)


def _utm_for_raster(raster: Raster) -> str:
    """The UTM zone containing the raster's centre, via its geographic centroid."""
    west, south, east, north = raster.bounds
    centre_x, centre_y = (west + east) / 2.0, (south + north) / 2.0

    source_crs = rasterio.crs.CRS.from_string(raster.spec.crs)
    if not source_crs.is_geographic:
        from rasterio.warp import transform as warp_points

        lons, lats = warp_points(source_crs, "EPSG:4326", [centre_x], [centre_y])
        centre_x, centre_y = lons[0], lats[0]

    return utm_epsg_for(centre_x, centre_y)
