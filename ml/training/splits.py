"""How the benchmark chips are divided into training and validation sets.

The split is by REGION, not by chip
------------------------------------
This is the decision that most easily invalidates a result, and it is invisible
once made wrongly.

Sen1Floods11 chips are 512x512 tiles cut from a much smaller number of flood
events. Two Ghana chips are two windows onto the same river, the same week, the
same sensor geometry and the same soil. Put one in training and the other in
validation and the model does not have to generalise to score well — it has
already seen that terrain, that speckle statistic, that water body. The
validation number then measures memorisation and reports it as skill.

Splitting by region makes validation answer the question the product actually
asks: *given a flood somewhere we have never processed, how well do we do?* The
score is lower and it is the true one.

The cost, stated plainly
------------------------
Sixty chips across seven regions is small. Holding out whole regions means the
validation set is a handful of events, so the estimate is noisy and moves with
which regions are held out. That is a real weakness of this evaluation and it is
recorded rather than hidden — but the alternative, a chip-level random split,
does not reduce the noise. It hides it behind a number that is wrong in a
flattering direction.

Why India is in validation
--------------------------
The product is for Indian flooding. A held-out Indian region is the closest thing
this dataset offers to the deployment condition, so India is always in validation
and never in training. A model that scores well on India *because it trained on
India* would tell us nothing about the demo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

#: Regions held out for validation. Fixed rather than randomised, so that two runs
#: of the training script are comparable — a moving split makes every comparison
#: between two models partly a comparison between two validation sets.
#:
#: India: the deployment condition, and the only region whose score speaks to the
#: demo. Somalia: the hardest region for the deterministic baseline (IoU 0.047,
#: ADR-0007 D13), so it keeps a genuinely difficult case in view rather than
#: letting the mean hide it.
VALIDATION_REGIONS: frozenset[str] = frozenset({"India", "Somalia"})

#: Region names may contain hyphens -- Sen1Floods11 has ``Sri-Lanka``. Kept in step
#: with ``_SAFE_STEM`` in fetch_sen1floods11.py; a name the fetcher accepts must be
#: a name the splitter can read, or chips land on disk that nothing can use.
_STEM = re.compile(r"^(?P<region>[A-Za-z]+(?:-[A-Za-z]+)*)_(?P<id>\d+)$")


class SplitError(ValueError):
    """The chips on disk cannot be split as configured."""


class Labelling(str, Enum):
    """Where a chip's labels came from, and therefore what it may be used for.

    Carried on every chip rather than inferred from a path at the point of use,
    because the one thing that must never happen is a weakly-labelled chip being
    scored as if it were ground truth. A published number measured against Otsu
    output is a measurement of Otsu, not of the model.
    """

    #: Drawn by a person. The only labelling any reported number may be measured
    #: against.
    HAND = "hand"
    #: Derived automatically -- Sentinel-2 spectral indices, or Otsu on VH.
    #: Training only, and enforced as such in :func:`split_by_region`.
    WEAK = "weak"


@dataclass(frozen=True)
class Chip:
    """One benchmark sample: the scene, its labels, and where it came from."""

    stem: str
    region: str
    scene: Path
    label: Path
    permanent_water: Path | None
    labelling: Labelling = Labelling.HAND

    @property
    def name(self) -> str:
        return self.stem


@dataclass(frozen=True)
class Split:
    train: tuple[Chip, ...]
    validation: tuple[Chip, ...]
    #: Weakly-labelled chips discarded because they come from a held-out region.
    #: Reported rather than silently dropped: it can be a large fraction of the
    #: data, and a run that quietly threw away a third of its training set should
    #: not look identical to one that did not.
    discarded: tuple[Chip, ...] = ()

    def summary(self) -> str:
        def describe(chips: Sequence[Chip]) -> str:
            regions = sorted({c.region for c in chips})
            hand = sum(1 for c in chips if c.labelling is Labelling.HAND)
            weak = len(chips) - hand
            counts = f"{len(chips):5d} chips ({hand} hand, {weak} weak)"
            return f"{counts}  {', '.join(regions)}"

        lines = [
            f"train      {describe(self.train)}",
            f"validation {describe(self.validation)}",
        ]
        if self.discarded:
            regions = sorted({c.region for c in self.discarded})
            lines.append(
                f"discarded  {len(self.discarded):5d} weakly-labelled chips from the "
                f"held-out regions ({', '.join(regions)})"
            )
        return "\n".join(lines)


def region_of(stem: str) -> str:
    """Extract the region from a chip stem such as ``India_1050276``."""
    match = _STEM.match(stem)
    if match is None:
        raise SplitError(f"cannot read a region from chip name {stem!r}; expected <Region>_<id>")
    return match.group("region")


def discover_chips(root: Path) -> tuple[Chip, ...]:
    """Find every chip under ``root`` that has both a scene and a label.

    A scene without labels is skipped rather than half-loaded: it cannot be
    trained on and it cannot be scored, so carrying it forward only produces a
    confusing failure later.
    """
    chips = [*_discover_hand(root), *_discover_weak(root)]
    if not chips:
        raise SplitError(
            f"no chips under {root.resolve()}.\n"
            "Fetch them first, from a normal shell:\n"
            "    python3 fetch_sen1floods11.py --count 60\n"
            "    python3 fetch_sen1floods11.py --dataset weak --count 4400"
        )
    return tuple(chips)


def _discover_hand(root: Path) -> list[Chip]:
    chips: list[Chip] = []
    for scene in sorted((root / "S1Hand").glob("*_S1Hand.tif")):
        stem = scene.name.replace("_S1Hand.tif", "")
        label = root / "LabelHand" / f"{stem}_LabelHand.tif"
        if not label.is_file():
            continue
        permanent = root / "JRCWaterHand" / f"{stem}_JRCWaterHand.tif"
        chips.append(
            Chip(
                stem=stem,
                region=region_of(stem),
                scene=scene,
                label=label,
                permanent_water=permanent if permanent.is_file() else None,
                labelling=Labelling.HAND,
            )
        )
    return chips


def _discover_weak(root: Path) -> list[Chip]:
    """Weakly-labelled chips, preferring the Sentinel-2 label over the Otsu one.

    Preference, not exclusivity. S2IndexLabelWeak sees water directly through
    spectral indices; S1OtsuLabelWeak infers it from radar darkness and inherits
    every failure mode the deterministic baseline has -- including inventing a
    flood on dry ground (ADR-0007 D13). Training on Otsu labels alone would teach
    the model to imitate the method it is meant to beat.

    But S2 labels are absent wherever there was no usable optical overpass, and a
    chip with only an Otsu label still carries real SAR imagery. Taking it is worth
    more than discarding it, so long as the better label wins when both exist.

    These chips have no JRC layer: the weakly-labelled set does not ship one. The
    prior channel therefore reads PRIOR_UNKNOWN for all of them, which is a state
    the model already trains on.
    """
    chips: list[Chip] = []
    for scene in sorted((root / "S1Weak").glob("*_S1Weak.tif")):
        stem = scene.name.replace("_S1Weak.tif", "")
        label = next(
            (
                candidate
                for candidate in (
                    root / "S2IndexLabelWeak" / f"{stem}_S2IndexLabelWeak.tif",
                    root / "S1OtsuLabelWeak" / f"{stem}_S1OtsuLabelWeak.tif",
                )
                if candidate.is_file()
            ),
            None,
        )
        if label is None:
            continue
        chips.append(
            Chip(
                stem=stem,
                region=region_of(stem),
                scene=scene,
                label=label,
                permanent_water=None,
                labelling=Labelling.WEAK,
            )
        )
    return chips


def split_by_region(
    chips: Iterable[Chip],
    *,
    validation_regions: frozenset[str] = VALIDATION_REGIONS,
) -> Split:
    """Divide chips into train and validation with no region on both sides.

    Raises
    ------
    SplitError
        If a configured validation region is not present on disk, or if either
        side of the split would be empty. Both are silent disasters otherwise: a
        misspelled region name yields an empty validation set, and an empty
        validation set makes every epoch report ``nan`` while training continues
        happily.
    """
    chips = tuple(chips)
    present = {c.region for c in chips}

    missing = validation_regions - present
    if missing:
        raise SplitError(
            f"validation regions {sorted(missing)} are not present on disk. "
            f"Available: {sorted(present)}. A misspelled region name would "
            "otherwise produce an empty validation set and a training run whose "
            "every epoch reports nan."
        )

    held_out = tuple(c for c in chips if c.region in validation_regions)

    train = tuple(c for c in chips if c.region not in validation_regions)

    # Two separate rules, and conflating them is the trap.
    #
    # 1. Validation is hand-labelled only. A number measured against Otsu output is
    #    a measurement of Otsu, not of the model, and it would be reported as
    #    accuracy.
    # 2. A weakly-labelled chip from a held-out region is DISCARDED, not moved into
    #    training. Moving it is the obvious thing to do -- it has no hand label, so
    #    it cannot be validated on, so it may as well be trained on -- and it
    #    silently destroys the entire point of holding regions out. The model would
    #    train on Indian terrain and then be scored on Indian terrain, and the
    #    held-out score would measure memorisation while looking like generalisation.
    validation = tuple(c for c in held_out if c.labelling is Labelling.HAND)
    discarded = tuple(c for c in held_out if c.labelling is not Labelling.HAND)

    if not train:
        raise SplitError("the training split is empty: every region is held out")
    if not validation:
        raise SplitError(
            "the validation split is empty: the held-out regions "
            f"{sorted(validation_regions)} contain no hand-labelled chips. "
            "Weakly-labelled chips cannot be validated against -- scoring a model "
            "on automatically derived labels measures the label generator."
        )

    overlap = {c.region for c in train} & {c.region for c in validation}
    if overlap:  # pragma: no cover - defensive; the comprehensions above prevent it
        raise SplitError(f"region leakage between splits: {sorted(overlap)}")

    return Split(train=train, validation=validation, discarded=discarded)
