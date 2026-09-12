"""Turn a raw threshold mask into something worth reporting as a flood extent.

A thresholded SAR scene is not a flood map. It is a map of everything darker than
a number, which includes the flood and also: single-pixel speckle troughs, radar
shadow behind buildings and terrain, smooth asphalt, dry sand, and every permanent
river and lake in the scene. Reporting that raw is how a system claims a car park
is inundated.

Each step here removes one specific class of false positive, and each reports how
many pixels it removed. That reporting is not decoration -- it is what lets an
operator see that 40% of the "flood" was permanent water, which is the difference
between a number they can act on and a number they have to take on faith.

Order of operations, and why it is this order
---------------------------------------------
The steps are not commutative, and getting them the wrong way round produces a
plausible mask rather than an error.

  1. subtract permanent water
  2. morphological opening      -- remove speckle
  3. fill enclosed holes
  4. subtract permanent water AGAIN
  5. minimum mapping unit       -- drop components too small to report

Permanent water is subtracted first because morphology should operate on the
flood, not on a river running through it. It is subtracted *again* after hole
filling because ``binary_fill_holes`` fills any False region fully enclosed by
True: a lake sitting inside a flooded plain gets refilled, silently putting back
exactly what step 1 removed. The second subtraction costs one array operation and
closes that hole in the logic.

The minimum mapping unit runs last, after everything else has settled, because a
component's size is only meaningful once its shape is final -- and because
subtracting a river can leave thin slivers along its banks that are themselves
below the reporting threshold.

Why the MMU is in hectares
--------------------------
Because pixels are not a unit of area. The same 25-pixel component is 0.25 ha on a
10 m grid and 0.06 ha on a 5 m one, so a threshold expressed in pixels quietly
changes meaning when the provider changes -- and the provider is still an open
question (issue #14). The caller passes hectares and the pixel count is derived
from the actual pixel area of the actual raster.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from scipy import ndimage

#: Smallest area worth reporting as a distinct flood patch, in hectares.
#:
#: 0.5 ha is 50 pixels on a 10 m Sentinel-1 grid -- roughly a large building
#: footprint. It sits inside the 0.1-1 ha range Copernicus EMS rapid mapping uses,
#: and it is about the smallest patch a responder could act on separately.
#:
#: **Chosen operationally, deliberately NOT by maximising the score.** Swept
#: against the Sen1Floods11 hand labels (ADR-0007 D12), IoU keeps climbing to a
#: peak near 5 ha:
#:
#:      MMU ha      IoU    precision   recall
#:           0    0.203       0.294    0.696
#:         0.5    0.221       0.322    0.661
#:           2    0.243       0.356    0.609
#:           5    0.252       0.373    0.577
#:          50    0.215       0.349    0.363
#:
#: That is not the filter working. Precision at 0 ha is 0.294, so seven of every
#: ten detected pixels are wrong, and deleting most of the mask raises the average
#: simply because most of the mask is noise -- recall falls the whole way down the
#: column. Setting the MMU to 5 ha would buy 0.03 IoU on nine chips and ship a
#: system that cannot see a flooded neighbourhood. The precision is the U-Net's
#: job to fix; the MMU's job is to drop patches too small to act on.
DEFAULT_MIN_MAPPING_UNIT_HA = 0.5

#: Structuring element for the morphological steps: 4-connectivity, one iteration.
#:
#: Deliberately the gentlest option available. Opening with a larger element
#: erodes the *edges* of genuine flood polygons, and since flood extent is
#: dominated by perimeter on a fragmented inundation, that shows up directly in
#: the hectare figure. Removing speckle must not cost real extent.
_CROSS = ndimage.generate_binary_structure(2, 1)


@dataclass(frozen=True)
class PostprocessResult:
    """A cleaned mask and an account of what was taken out of it."""

    mask: npt.NDArray[np.bool_]
    removed_permanent_water_px: int = 0
    removed_speckle_px: int = 0
    filled_holes_px: int = 0
    removed_below_mmu_px: int = 0
    components_before: int = 0
    components_after: int = 0
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_removed_px(self) -> int:
        return (
            self.removed_permanent_water_px
            + self.removed_speckle_px
            + self.removed_below_mmu_px
            - self.filled_holes_px
        )


def postprocess_water_mask(
    mask: npt.NDArray[np.bool_],
    *,
    pixel_area_m2: float,
    permanent_water: npt.NDArray[np.bool_] | None = None,
    min_mapping_unit_ha: float = DEFAULT_MIN_MAPPING_UNIT_HA,
    remove_speckle: bool = True,
    fill_holes: bool = True,
) -> PostprocessResult:
    """Clean a raw threshold mask and report every pixel removed.

    Parameters
    ----------
    mask
        Boolean water mask, as produced by
        :func:`ml.pipeline.baseline.water_mask_single_date`.
    pixel_area_m2
        Ground area of one pixel, from
        :func:`ml.geo.area.pixel_area_m2`. Required rather than defaulted: the
        minimum mapping unit is meaningless without it, and a default of 100 m²
        would be silently wrong for every provider that is not Sentinel-1 at 10 m.
    permanent_water
        Mask of water that is always present. When omitted, the result carries a
        caveat saying so -- absence of a permanent-water layer is a limitation of
        the answer and the reader is entitled to know.
    min_mapping_unit_ha
        Components smaller than this are dropped. Set to ``0`` to disable, which
        is occasionally right for a narrow-channel study and almost never right
        otherwise.

    Raises
    ------
    ValueError
        If ``pixel_area_m2`` is not a positive finite number, if ``mask`` is not
        2-D, or if ``permanent_water`` is not co-registered with ``mask``.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {mask.shape}")
    if not math.isfinite(pixel_area_m2) or pixel_area_m2 <= 0:
        raise ValueError(f"pixel_area_m2 must be positive and finite, got {pixel_area_m2!r}")
    if min_mapping_unit_ha < 0:
        raise ValueError(f"min_mapping_unit_ha must not be negative, got {min_mapping_unit_ha}")

    working = np.asarray(mask, dtype=bool)
    caveats: list[str] = []
    components_before = _count_components(working)

    removed_permanent = 0
    if permanent_water is not None:
        if permanent_water.shape != working.shape:
            raise ValueError(
                f"permanent_water is {permanent_water.shape} but the mask is "
                f"{working.shape}; they must be co-registered before subtraction"
            )
        permanent = np.asarray(permanent_water, dtype=bool)
        before = int(np.count_nonzero(working))
        working = working & ~permanent
        removed_permanent = before - int(np.count_nonzero(working))
    else:
        permanent = None
        caveats.append(
            "no permanent-water layer supplied: rivers and lakes present before the "
            "event are counted in this extent"
        )

    removed_speckle = 0
    if remove_speckle:
        before = int(np.count_nonzero(working))
        working = ndimage.binary_opening(working, structure=_CROSS)
        removed_speckle = before - int(np.count_nonzero(working))

    filled_holes = 0
    if fill_holes:
        before = int(np.count_nonzero(working))
        working = ndimage.binary_fill_holes(working, structure=_CROSS)
        filled_holes = int(np.count_nonzero(working)) - before

        # Second subtraction. binary_fill_holes fills any False region fully
        # enclosed by True, so a lake inside a flooded plain is put straight back.
        if permanent is not None:
            before = int(np.count_nonzero(working))
            working = working & ~permanent
            refilled = before - int(np.count_nonzero(working))
            removed_permanent += refilled
            filled_holes -= refilled

    removed_below_mmu = 0
    if min_mapping_unit_ha > 0:
        minimum_pixels = _hectares_to_pixels(min_mapping_unit_ha, pixel_area_m2)
        if minimum_pixels > 1:
            before = int(np.count_nonzero(working))
            working = _drop_small_components(working, minimum_pixels)
            removed_below_mmu = before - int(np.count_nonzero(working))
            caveats.append(
                f"components below {min_mapping_unit_ha} ha "
                f"({minimum_pixels} px at {pixel_area_m2:.1f} m2/px) removed"
            )

    if removed_permanent:
        hectares = removed_permanent * pixel_area_m2 / 10_000.0
        caveats.append(f"{hectares:.1f} ha of permanent water subtracted")
    if removed_speckle:
        caveats.append(f"{removed_speckle} px removed as speckle (morphological opening)")
    if filled_holes:
        caveats.append(f"{filled_holes} px filled as enclosed holes")

    return PostprocessResult(
        mask=working,
        removed_permanent_water_px=removed_permanent,
        removed_speckle_px=removed_speckle,
        filled_holes_px=filled_holes,
        removed_below_mmu_px=removed_below_mmu,
        components_before=components_before,
        components_after=_count_components(working),
        caveats=tuple(caveats),
    )


def _hectares_to_pixels(hectares: float, pixel_area_m2: float) -> int:
    """Convert a reporting threshold in hectares to a pixel count for this grid.

    Rounds up: a component exactly at the threshold should be kept, and rounding
    down would drop it. When in doubt about a real detection, keep it and let the
    caveat explain -- silently deleting observed water is the worse error of the
    two, because nothing downstream can tell it happened.
    """
    return int(math.ceil(hectares * 10_000.0 / pixel_area_m2))


def _count_components(mask: npt.NDArray[np.bool_]) -> int:
    _, count = ndimage.label(mask, structure=_CROSS)
    return int(count)


def _drop_small_components(
    mask: npt.NDArray[np.bool_], minimum_pixels: int
) -> npt.NDArray[np.bool_]:
    """Remove connected components smaller than ``minimum_pixels``.

    4-connectivity, matching the morphology above: under 8-connectivity two
    speckle pixels touching only at a corner become one component, which is not a
    water body by any physical reading and would survive a size filter that a
    diagonal link had inflated past the threshold.
    """
    labels, count = ndimage.label(mask, structure=_CROSS)
    if count == 0:
        return mask

    # Index 0 is the background; the slice drops it before comparing sizes.
    sizes = np.bincount(labels.ravel())
    keep = sizes >= minimum_pixels
    keep[0] = False
    kept: npt.NDArray[np.bool_] = keep[labels]
    return kept
