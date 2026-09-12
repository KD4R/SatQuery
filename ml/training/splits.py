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


@dataclass(frozen=True)
class Chip:
    """One benchmark sample: the scene, its labels, and where it came from."""

    stem: str
    region: str
    scene: Path
    label: Path
    permanent_water: Path | None

    @property
    def name(self) -> str:
        return self.stem


@dataclass(frozen=True)
class Split:
    train: tuple[Chip, ...]
    validation: tuple[Chip, ...]

    def summary(self) -> str:
        def describe(chips: Sequence[Chip]) -> str:
            regions = sorted({c.region for c in chips})
            return f"{len(chips):3d} chips  {', '.join(regions)}"

        return f"train      {describe(self.train)}\n" f"validation {describe(self.validation)}"


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
    scenes = sorted((root / "S1Hand").glob("*_S1Hand.tif"))
    if not scenes:
        raise SplitError(
            f"no chips under {root.resolve()}.\n"
            "Fetch them first, from a normal shell:\n"
            "    python3 fetch_sen1floods11.py --count 60"
        )

    chips: list[Chip] = []
    for scene in scenes:
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
            )
        )
    return tuple(chips)


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

    train = tuple(c for c in chips if c.region not in validation_regions)
    validation = tuple(c for c in chips if c.region in validation_regions)

    if not train:
        raise SplitError("the training split is empty: every region is held out")
    if not validation:
        raise SplitError("the validation split is empty")

    overlap = {c.region for c in train} & {c.region for c in validation}
    if overlap:  # pragma: no cover - defensive; the comprehensions above prevent it
        raise SplitError(f"region leakage between splits: {sorted(overlap)}")

    return Split(train=train, validation=validation)
