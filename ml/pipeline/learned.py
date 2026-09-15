"""Running the learned model over a whole raster.

One implementation, used by everything
---------------------------------------
The inference service and the report generator both need "model plus raster gives
mask". Written twice they drift, and the way they drift is subtle: the first
version of the report generator scored the model on the *native* grid while
scoring the baseline on the *reprojected* one, and the only reason it did not
silently report a wrong comparison is that the two arrays had different shapes and
``confusion`` refused them.

That refusal was luck. Had the chip been square after reprojection the numbers
would have been produced, looked plausible, and been wrong. So the logic lives
here, and both callers import it.

torch is imported inside the function. Everything else in ``ml/`` runs without a
deep-learning stack, and that property is what lets the contracts, the geometry
and the baseline be tested in the ordinary CI job.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from packages.contracts import Polarization
from ml.io.raster import Raster

#: Band order the models are trained on. Fetched from the raster BY NAME, never by
#: index -- ml/io/raster.py explains why positional access is how the band-order
#: defect propagates.
MODEL_BANDS: tuple[Polarization, ...] = (Polarization.VV, Polarization.VH)

#: Probability above which a pixel is called water. Swept against the held-out set
#: (ADR-0007 D14): 0.5 is near-optimal, and no threshold rescues the dry chips, so
#: this is a constant rather than a knob. A caller tuning it per request would be
#: tuning the reported area.
WATER_THRESHOLD = 0.5


def predict_water_probability(
    model: Any,
    normalisation: Any,
    raster: Raster,
    permanent_water: npt.NDArray[np.bool_] | None = None,
) -> npt.NDArray[np.float32]:
    """Per-pixel water probability, on the raster's own grid.

    The output has exactly the input's height and width. That matters more than it
    sounds: the caller compares it against labels, and a mask on a different grid
    from its truth is either a crash or a wrong number depending on whether the
    shapes happen to match.
    """
    import torch

    from ml.training.dataset import PRIOR_PERMANENT, PRIOR_SEASONAL_OR_DRY, prepare

    bands = np.stack([raster.band(p) for p in MODEL_BANDS]).astype(np.float32)

    # The channel count comes off the checkpoint, never off the data. A two-channel
    # model must not be handed three because a JRC layer happened to be available,
    # and a three-channel model must still run when it is not -- it was trained with
    # the prior dropped a quarter of the time precisely so that it can.
    include_prior = getattr(model, "in_channels", len(MODEL_BANDS)) > len(MODEL_BANDS)
    prior = None
    if include_prior and permanent_water is not None:
        prior = np.where(permanent_water, PRIOR_PERMANENT, PRIOR_SEASONAL_OR_DRY).astype(np.float32)
    # prepare() wants labels to build its validity mask; at inference there are
    # none, so zeros are passed and the returned mask discarded. Only the
    # standardised bands are used -- and standardising with the checkpoint's own
    # constants, not freshly fitted ones, is what keeps inference consistent with
    # training.
    standardised, _, _ = prepare(
        bands,
        np.zeros(bands.shape[1:], dtype=np.int16),
        normalisation,
        prior,
        include_prior=include_prior,
    )

    tensor = torch.from_numpy(standardised).unsqueeze(0)
    height, width = tensor.shape[-2:]

    # Pad up to a multiple the encoder's poolings divide evenly, then crop back.
    # Reflection, not zeros: zero is the post-standardisation mean, so a zero
    # border reads as ordinary land and can pull predictions at the image edge.
    multiple = 2**model.depth
    pad_h, pad_w = (-height) % multiple, (-width) % multiple
    if pad_h or pad_w:
        tensor = torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")

    with torch.no_grad():
        logits = model(tensor)

    if pad_h:
        logits = logits[..., :-pad_h, :]
    if pad_w:
        logits = logits[..., :, :-pad_w]

    probabilities: npt.NDArray[np.float32] = (
        torch.sigmoid(logits).squeeze(0).numpy().astype(np.float32)
    )
    if probabilities.shape != (height, width):  # pragma: no cover - defensive
        raise RuntimeError(
            f"prediction is {probabilities.shape} but the raster is "
            f"{(height, width)}; the pad/crop is wrong and every metric computed "
            "from this would be meaningless"
        )
    return probabilities


def predict_water_mask(
    model: Any,
    normalisation: Any,
    raster: Raster,
    permanent_water: npt.NDArray[np.bool_] | None = None,
    *,
    threshold: float = WATER_THRESHOLD,
) -> npt.NDArray[np.bool_]:
    """Boolean water mask, on the raster's own grid."""
    probability = predict_water_probability(model, normalisation, raster, permanent_water)
    mask: npt.NDArray[np.bool_] = probability >= threshold
    return mask
