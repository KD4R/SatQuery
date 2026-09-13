"""Turning benchmark chips into training samples.

Three decisions here do more for the result than the model architecture does.

**Dry chips stay in.** ADR-0007 D13 measured the deterministic baseline at IoU
0.704 on chips with more than 30% water and 0.004 on chips with less than 1%. The
failure is not a blurry boundary, it is that Otsu always splits a histogram and so
invents a flood on a dry scene. A model only learns to say *no water here* if dry
scenes are in its training set, so the obvious-looking optimisation — drop the
chips with nothing to segment, they contribute no positive pixels — would remove
precisely the capability the model is being added to provide.

**Normalisation constants are fixed and computed from the training split only.**
Per-chip standardisation is tempting and wrong twice over: it leaks each chip's
own statistics into its prediction, and it makes a flooded scene and a dry scene
look alike, since it is exactly the dark tail that distinguishes them. Statistics
from the validation split would leak the other way. So the constants are computed
once over training chips and saved beside the checkpoint, and inference reuses
them rather than recomputing.

**No-data is a third class, never background.** Sen1Floods11 marks chip borders
``-1``. Training those as land teaches the model that the edge of every image is
dry, and scoring them as correct background inflates every metric. They are
carried through as an ignore mask and excluded from the loss.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import rasterio

from packages.contracts import BackscatterScale, Polarization
from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE
from ml.io.raster import read_raster
from ml.training.splits import Chip

#: The two bands the model consumes, in the order it consumes them.
#: Read by name from the validated raster, never by position -- see ml/io/raster.py
#: on why positional band access is how the band-order defect propagates.
MODEL_BANDS: tuple[Polarization, ...] = (Polarization.VV, Polarization.VH)

#: Sen1Floods11 chips are stored in decibels. Declared, never inferred (D3).
CHIP_SCALE = BackscatterScale.DECIBEL

#: Value substituted for NaN after standardisation. Zero is the post-standardisation
#: mean, so an invalid pixel becomes "unremarkable" rather than "extremely dark" --
#: which is what a raw NaN-to--50dB substitution would make it, and the model would
#: learn that no-data means water.
FILL_AFTER_STANDARDISATION = 0.0


@dataclass(frozen=True)
class Normalisation:
    """Per-band mean and standard deviation, fitted on the training split."""

    mean: tuple[float, ...]
    std: tuple[float, ...]

    def apply(self, bands: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        mean = np.asarray(self.mean, dtype=np.float32).reshape(-1, 1, 1)
        std = np.asarray(self.std, dtype=np.float32).reshape(-1, 1, 1)
        result: npt.NDArray[np.float32] = (bands - mean) / std
        return result

    def to_dict(self) -> dict[str, list[float]]:
        return {"mean": list(self.mean), "std": list(self.std)}

    @classmethod
    def from_dict(cls, payload: dict[str, list[float]]) -> Normalisation:
        return cls(mean=tuple(payload["mean"]), std=tuple(payload["std"]))


def load_chip(chip: Chip) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.int16]]:
    """Read one chip as (bands, labels), on the file's own grid.

    No reprojection. Training happens on the native grid because the model learns
    from pixel neighbourhoods, not from ground distances, and resampling every chip
    would blur the speckle statistics the network needs. Reprojection is a
    measurement concern and happens at inference, before area is computed.
    """
    raster = read_raster(chip.scene, declared_band_order=MODEL_BANDS, declared_scale=CHIP_SCALE)
    bands = np.stack([raster.band(p) for p in MODEL_BANDS]).astype(np.float32)

    with rasterio.open(chip.label) as source:
        labels = source.read(1).astype(np.int16)

    if labels.shape != bands.shape[1:]:
        raise ValueError(
            f"{chip.stem}: label grid {labels.shape} does not match scene grid "
            f"{bands.shape[1:]}; they must be co-registered"
        )
    return bands, labels


#: Encoding of the permanent-water prior channel. Three states, not two, because
#: "this chip has no JRC layer" and "this pixel is not permanent water" are
#: different claims and a binary channel cannot tell them apart. Feeding 0 for both
#: would teach the model that a missing layer means dry ground everywhere -- which
#: is exactly the input it will see in production the first time the JRC fetch
#: fails, and it would confidently report a flood over a lake.
PRIOR_UNKNOWN = 0.0
PRIOR_PERMANENT = 1.0
PRIOR_SEASONAL_OR_DRY = -1.0

#: Fraction of training samples whose prior channel is blanked to PRIOR_UNKNOWN.
#:
#: Without this the model comes to depend on the layer, and the service degrades
#: to nonsense rather than to the SAR-only answer whenever JRC is unavailable --
#: which the inference service already treats as an ordinary, non-fatal condition
#: (permanent_water_href is optional). Dropout makes "no prior" a case the model
#: has trained on rather than one it meets for the first time in production.
PRIOR_DROPOUT = 0.25


def load_permanent_water_prior(
    chip: Chip, shape: tuple[int, ...]
) -> npt.NDArray[np.float32] | None:
    """The JRC permanent-water layer as a prior channel, or None if absent.

    Why this helps, given that postprocessing already subtracts permanent water:
    subtraction happens *after* the model has already decided, so the model still
    spends capacity learning that certain dark regions are not floods. As an input
    it is told, and can spend that capacity on the boundary cases instead. The
    subtraction stays -- it is a measurement rule, not a modelling one.

    Read on the chip's own grid with no resampling. Sen1Floods11 ships every layer
    co-registered, so a shape mismatch means the wrong file, and guessing a
    reprojection here would hide that.
    """
    if chip.permanent_water is None:
        return None

    with rasterio.open(chip.permanent_water) as source:
        layer = source.read(1)

    if layer.shape != shape:
        raise ValueError(
            f"{chip.stem}: permanent-water grid {layer.shape} does not match the "
            f"scene grid {shape}; they are meant to be co-registered, so this is a "
            "mismatched file rather than something to resample away"
        )

    prior = np.where(layer == 1, PRIOR_PERMANENT, PRIOR_SEASONAL_OR_DRY)
    return prior.astype(np.float32)


def fit_normalisation(chips: tuple[Chip, ...]) -> Normalisation:
    """Compute per-band mean and standard deviation over the training chips.

    NaN-aware, and pooled across chips rather than averaged per chip: a chip with
    fewer valid pixels should contribute proportionally less, not equally.
    """
    if not chips:
        raise ValueError("cannot fit normalisation on an empty split")

    totals = np.zeros(len(MODEL_BANDS), dtype=np.float64)
    squares = np.zeros(len(MODEL_BANDS), dtype=np.float64)
    counts = np.zeros(len(MODEL_BANDS), dtype=np.int64)

    for chip in chips:
        bands, _ = load_chip(chip)
        for index in range(bands.shape[0]):
            values = bands[index]
            finite = values[np.isfinite(values)]
            totals[index] += float(finite.sum())
            squares[index] += float(np.square(finite.astype(np.float64)).sum())
            counts[index] += finite.size

    if np.any(counts == 0):
        raise ValueError("a band has no finite samples across the training split")

    mean = totals / counts
    variance = np.maximum(squares / counts - np.square(mean), 1e-6)
    return Normalisation(
        mean=tuple(float(v) for v in mean),
        std=tuple(float(v) for v in np.sqrt(variance)),
    )


def prepare(
    bands: npt.NDArray[np.float32],
    labels: npt.NDArray[np.int16],
    normalisation: Normalisation,
    prior: npt.NDArray[np.float32] | None = None,
    *,
    include_prior: bool = False,
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """Standardise and split labels into a target and a validity mask.

    Returns ``(x, y, weight)`` where ``weight`` is 1 on scorable pixels and 0 on
    no-data. The loss multiplies by it, so no-data contributes no gradient. Coming
    out of here, ``y`` is only ever 0 or 1 -- the ``-1`` never reaches the model.

    ``include_prior`` appends the permanent-water channel, giving three channels
    instead of two. It is a flag rather than "append it whenever a prior was
    passed" because the channel count has to match the checkpoint's architecture
    exactly, and inferring it from whether a file happened to be on disk would make
    the input shape depend on the filesystem. Callers read it off the model
    (``model.in_channels``), never off the data.

    With ``include_prior`` and no prior, the channel is PRIOR_UNKNOWN throughout --
    a state the model has seen in training, because of PRIOR_DROPOUT.
    """
    standardised = normalisation.apply(bands)

    if include_prior:
        if prior is None:
            prior = np.full(bands.shape[1:], PRIOR_UNKNOWN, dtype=np.float32)
        elif prior.shape != bands.shape[1:]:
            raise ValueError(f"prior is {prior.shape} but the bands are {bands.shape[1:]}")
        standardised = np.concatenate([standardised, prior[np.newaxis]], axis=0)

    # NaN must not reach the network: a single NaN propagates through the
    # convolutions and makes the whole loss NaN, which looks like a diverged model
    # rather than a data problem and costs an afternoon to trace.
    invalid_pixels = ~np.isfinite(standardised)
    standardised = np.where(invalid_pixels, FILL_AFTER_STANDARDISATION, standardised)

    scorable = labels != SEN1FLOODS11_IGNORE_VALUE
    # A pixel with no observation cannot be learned from even if it carries a
    # label, so validity is the intersection of "labelled" and "observed".
    observed = ~np.any(invalid_pixels, axis=0)
    weight = (scorable & observed).astype(np.float32)

    target = (labels == 1).astype(np.float32)
    return standardised.astype(np.float32), target, weight


def random_crop(
    x: npt.NDArray[np.float32],
    y: npt.NDArray[np.float32],
    weight: npt.NDArray[np.float32],
    *,
    size: int,
    rng: np.random.Generator,
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """Take a random ``size`` x ``size`` window.

    Crops rather than full chips for two reasons: 512x512 activations do not fit
    comfortably in the 3 GB available, and a crop is a genuine augmentation --
    sixty chips is a very small training set, and each epoch seeing different
    windows is most of what stops the model memorising them.

    Deliberately NOT biased toward crops containing water. That biasing is the
    standard trick for class imbalance and it would undo D13: the model needs to
    see dry ground to learn that dry ground exists.
    """
    _, height, width = x.shape
    if height < size or width < size:
        raise ValueError(f"chip is {height}x{width}, smaller than the {size} crop")

    top = int(rng.integers(0, height - size + 1))
    left = int(rng.integers(0, width - size + 1))
    window = (slice(top, top + size), slice(left, left + size))
    return x[(slice(None), *window)], y[window], weight[window]


def augment(
    x: npt.NDArray[np.float32],
    y: npt.NDArray[np.float32],
    weight: npt.NDArray[np.float32],
    rng: np.random.Generator,
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """Flips and 90-degree rotations only.

    These are the augmentations that are physically meaningful for SAR: a flood
    seen from the other side is still a flood. Brightness and contrast jitter are
    deliberately absent -- backscatter in decibels is a calibrated physical
    quantity, and shifting it teaches the model that the absolute value carries no
    information, when the absolute value is very nearly the whole signal.
    """
    if rng.random() < 0.5:
        x, y, weight = x[:, ::-1, :], y[::-1, :], weight[::-1, :]
    if rng.random() < 0.5:
        x, y, weight = x[:, :, ::-1], y[:, ::-1], weight[:, ::-1]
    turns = int(rng.integers(0, 4))
    if turns:
        x = np.rot90(x, turns, axes=(1, 2))
        y = np.rot90(y, turns)
        weight = np.rot90(weight, turns)
    return (
        np.ascontiguousarray(x),
        np.ascontiguousarray(y),
        np.ascontiguousarray(weight),
    )


class Sen1Floods11Dataset:
    """Chips as training samples. A torch ``Dataset`` without importing torch.

    Kept free of torch on purpose: the split logic, normalisation and cropping are
    the parts most likely to contain a silent defect, and keeping them as plain
    NumPy means they are testable in the ordinary CI job, which has no deep
    learning stack installed. ``ml/training/loader.py`` wraps this for torch.
    """

    def __init__(
        self,
        chips: tuple[Chip, ...],
        normalisation: Normalisation,
        *,
        crop_size: int | None = 256,
        augment_samples: bool = True,
        seed: int = 0,
        cache: bool = True,
        include_prior: bool = False,
        prior_dropout: float = PRIOR_DROPOUT,
    ) -> None:
        if not chips:
            raise ValueError("dataset is empty")
        if not 0.0 <= prior_dropout <= 1.0:
            raise ValueError(f"prior_dropout must be a probability, got {prior_dropout}")
        self.chips = chips
        self.normalisation = normalisation
        self.crop_size = crop_size
        self.augment_samples = augment_samples
        self.include_prior = include_prior
        self.prior_dropout = prior_dropout
        self._rng = np.random.default_rng(seed)
        self._cache: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] | None = (
            {} if cache else None
        )

    def __len__(self) -> int:
        return len(self.chips)

    def clear_cache(self) -> None:
        """Drop cached samples.

        Needed whenever ``normalisation`` is replaced after construction -- the
        cache holds already-standardised arrays, so a new normalisation that does
        not clear it would apply to new chips only, and the model would train on a
        set standardised two different ways with nothing to show for it but a
        worse score.
        """
        if self._cache is not None:
            self._cache.clear()

    def _prepared(self, index: int):
        if self._cache is not None and index in self._cache:
            return self._cache[index]
        chip = self.chips[index]
        bands, labels = load_chip(chip)
        prior = load_permanent_water_prior(chip, bands.shape[1:]) if self.include_prior else None
        prepared = prepare(
            bands, labels, self.normalisation, prior, include_prior=self.include_prior
        )
        if self._cache is not None:
            self._cache[index] = prepared
        return prepared

    def __getitem__(self, index: int):
        x, y, weight = self._prepared(index)
        if self.include_prior and self._rng.random() < self.prior_dropout:
            # Blank the prior, do not remove it: the channel count is fixed by the
            # architecture. The model sees PRIOR_UNKNOWN often enough in training
            # that a missing JRC layer at inference is a case it has met, not a
            # distribution it has never been shown.
            #
            # Copied first because _prepared() caches, and writing into the cached
            # array would blank that chip's prior permanently -- silently turning a
            # 25% dropout into a one-way ratchet over the run.
            x = x.copy()
            x[-1] = PRIOR_UNKNOWN
        if self.crop_size is not None:
            x, y, weight = random_crop(x, y, weight, size=self.crop_size, rng=self._rng)
        if self.augment_samples:
            x, y, weight = augment(x, y, weight, self._rng)
        return x, y, weight
