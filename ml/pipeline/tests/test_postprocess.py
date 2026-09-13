"""Tests for mask postprocessing.

Every array here is hand-built with a shape whose correct answer can be counted
by eye, so a failure points at the step rather than at the fixture.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.pipeline.postprocess import (
    DEFAULT_MIN_MAPPING_UNIT_HA,
    postprocess_water_mask,
)

pytestmark = pytest.mark.unit

TEN_METRE_PIXEL = 100.0  # m2


def a_block(size: int = 40, block: int = 20) -> np.ndarray:
    """A solid square of water in the middle of dry land."""
    mask = np.zeros((size, size), dtype=bool)
    mask[10 : 10 + block, 10 : 10 + block] = True
    return mask


# --------------------------------------------------------------------------- #
# Speckle                                                                      #
# --------------------------------------------------------------------------- #


def test_isolated_pixels_are_removed() -> None:
    """A single dark pixel is speckle, not a flood. Real water is contiguous."""
    mask = a_block()
    mask[0, 0] = True
    mask[39, 39] = True
    mask[0, 39] = True

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL)

    assert not result.mask[0, 0]
    assert not result.mask[39, 39]
    assert not result.mask[0, 39]
    assert result.mask[20, 20]  # the real block survives


def test_the_block_survives_speckle_removal_almost_intact() -> None:
    """Opening rounds convex corners, so it costs a little real extent.

    Pinned rather than hidden: the cost is four corner pixels on a 400-pixel
    block, which is 1%. If a future change makes the structuring element larger
    that number grows fast, and since flood extent is dominated by perimeter on
    fragmented inundation it would show up directly in the hectare figure.
    """
    mask = a_block()
    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, min_mapping_unit_ha=0)
    assert int(result.mask.sum()) >= int(mask.sum()) - 4


# --------------------------------------------------------------------------- #
# Holes                                                                        #
# --------------------------------------------------------------------------- #


def test_enclosed_holes_are_filled() -> None:
    """A flooded field with wind-roughened patches is still a flooded field."""
    mask = a_block()
    mask[15, 15] = False
    mask[16, 16] = False

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL)

    assert result.mask[15, 15]
    assert result.mask[16, 16]
    assert result.filled_holes_px >= 2


def test_a_bay_open_to_the_edge_is_not_filled() -> None:
    """Only *enclosed* holes are filled. A concave inlet is real shape."""
    mask = a_block()
    mask[10:20, 15] = False  # a channel cut through to the block's edge

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, remove_speckle=False)

    assert not result.mask[10, 15]


# --------------------------------------------------------------------------- #
# Minimum mapping unit                                                         #
# --------------------------------------------------------------------------- #


def test_components_below_the_minimum_mapping_unit_are_dropped() -> None:
    mask = np.zeros((60, 60), dtype=bool)
    mask[5:25, 5:25] = True  # 400 px = 4 ha at 10 m
    mask[40:44, 40:44] = True  # 16 px = 0.16 ha

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, min_mapping_unit_ha=0.5)

    assert result.mask[10, 10]
    assert not result.mask[41, 41]
    assert result.components_after == 1


def test_the_threshold_is_in_hectares_not_pixels() -> None:
    """The same patch must be kept or dropped by its ground area, not its pixel count.

    A 100-pixel patch is 1 ha on a 10 m grid and 0.25 ha on a 5 m one. Expressing
    the threshold in pixels would silently change what the system reports when the
    provider changes -- and the provider is still an open question (issue #14).
    """
    mask = np.zeros((40, 40), dtype=bool)
    mask[10:20, 10:20] = True  # 100 px

    kept = postprocess_water_mask(
        mask, pixel_area_m2=100.0, min_mapping_unit_ha=0.5, remove_speckle=False
    )
    dropped = postprocess_water_mask(
        mask, pixel_area_m2=25.0, min_mapping_unit_ha=0.5, remove_speckle=False
    )

    assert kept.mask.any()  # 1.00 ha on a 10 m grid -- above the threshold
    assert not dropped.mask.any()  # 0.25 ha on a 5 m grid -- below it


def test_a_zero_minimum_mapping_unit_disables_the_filter() -> None:
    mask = np.zeros((40, 40), dtype=bool)
    mask[10:14, 10:14] = True

    result = postprocess_water_mask(
        mask, pixel_area_m2=TEN_METRE_PIXEL, min_mapping_unit_ha=0, remove_speckle=False
    )
    assert result.mask.any()
    assert result.removed_below_mmu_px == 0


def test_diagonal_touching_specks_do_not_merge_into_a_reportable_patch() -> None:
    """4-connectivity, matching the morphology.

    Under 8-connectivity two speckle pixels touching only at a corner become one
    component, which is not a water body by any physical reading, and a chain of
    them could cross the size threshold that each individually fails.
    """
    mask = np.zeros((40, 40), dtype=bool)
    for i in range(0, 30, 2):
        mask[i, i] = True

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, min_mapping_unit_ha=0.05)
    assert not result.mask.any()


# --------------------------------------------------------------------------- #
# Permanent water                                                              #
# --------------------------------------------------------------------------- #


def test_permanent_water_is_subtracted() -> None:
    """A lake reported as flooding is the most embarrassing failure available."""
    mask = a_block()
    permanent = np.zeros_like(mask)
    permanent[10:20, 10:30] = True  # the upper half of the block is a lake

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, permanent_water=permanent)

    assert not result.mask[12, 12]
    assert result.removed_permanent_water_px > 0
    assert any("permanent water subtracted" in c for c in result.caveats)


def test_hole_filling_cannot_put_permanent_water_back() -> None:
    """The subtlest bug in this module, and the reason it is subtracted twice.

    ``binary_fill_holes`` fills any False region fully enclosed by True. A lake
    sitting inside a flooded plain becomes exactly that the moment it is
    subtracted, so a single subtraction before the morphology would be silently
    undone by it -- restoring the pixels that step existed to remove.
    """
    mask = np.zeros((40, 40), dtype=bool)
    mask[5:35, 5:35] = True  # a large flooded plain

    permanent = np.zeros_like(mask)
    permanent[18:22, 18:22] = True  # a small lake in the middle of it

    result = postprocess_water_mask(
        mask, pixel_area_m2=TEN_METRE_PIXEL, permanent_water=permanent, fill_holes=True
    )

    assert not result.mask[19, 19], "the lake was refilled by hole filling"
    assert result.mask[10, 10], "the surrounding flood should be untouched"


def test_missing_permanent_water_is_declared_as_a_caveat() -> None:
    """Not having the layer is a limitation of the answer, so the answer says so."""
    result = postprocess_water_mask(a_block(), pixel_area_m2=TEN_METRE_PIXEL)
    assert any("no permanent-water layer" in c for c in result.caveats)


def test_a_misregistered_permanent_water_mask_is_refused() -> None:
    with pytest.raises(ValueError, match="co-registered"):
        postprocess_water_mask(
            a_block(),
            pixel_area_m2=TEN_METRE_PIXEL,
            permanent_water=np.zeros((10, 10), dtype=bool),
        )


# --------------------------------------------------------------------------- #
# Input validation                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_a_nonsensical_pixel_area_is_refused(bad: float) -> None:
    """Without a real pixel area the minimum mapping unit means nothing.

    Defaulting it to 100 m2 would be silently wrong for every provider that is
    not Sentinel-1 at 10 m, which is why it has no default at all.
    """
    with pytest.raises(ValueError, match="pixel_area_m2"):
        postprocess_water_mask(a_block(), pixel_area_m2=bad)


def test_a_non_two_dimensional_mask_is_refused() -> None:
    with pytest.raises(ValueError, match="2-D"):
        postprocess_water_mask(np.zeros((2, 10, 10), dtype=bool), pixel_area_m2=TEN_METRE_PIXEL)


def test_a_negative_minimum_mapping_unit_is_refused() -> None:
    with pytest.raises(ValueError, match="min_mapping_unit_ha"):
        postprocess_water_mask(a_block(), pixel_area_m2=TEN_METRE_PIXEL, min_mapping_unit_ha=-1.0)


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #


def test_an_empty_mask_survives_every_step_without_error() -> None:
    """No water detected is a real answer, not an edge case to crash on."""
    result = postprocess_water_mask(np.zeros((40, 40), dtype=bool), pixel_area_m2=TEN_METRE_PIXEL)
    assert not result.mask.any()
    assert result.components_after == 0


def test_every_removal_is_reported() -> None:
    """The counts are what let an operator see that 40% of the "flood" was a river.

    Without them the cleaned number is less trustworthy than the raw one, because
    the reader cannot tell what was taken out.
    """
    mask = a_block()
    mask[0, 0] = True
    mask[15, 15] = False
    permanent = np.zeros_like(mask)
    permanent[10:14, 10:14] = True

    result = postprocess_water_mask(mask, pixel_area_m2=TEN_METRE_PIXEL, permanent_water=permanent)

    assert result.removed_speckle_px > 0
    assert result.removed_permanent_water_px > 0
    assert result.filled_holes_px >= 1
    assert len(result.caveats) >= 3


def test_the_default_minimum_mapping_unit_is_operationally_sized() -> None:
    """Pinned so that a future "optimisation" to whatever maximises IoU is visible.

    The sweep in ADR-0007 D12 shows IoU still rising at 5 ha, because the
    baseline's precision is 0.29 and deleting most of the mask improves the
    average. 5 ha cannot see a flooded neighbourhood. This value is chosen for
    what it means on the ground, not for what it scores.
    """
    assert DEFAULT_MIN_MAPPING_UNIT_HA == 0.5
