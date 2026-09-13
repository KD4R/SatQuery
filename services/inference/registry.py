"""The model registry: which models exist, what they scored, and which one ran.

Why a registry rather than a global
------------------------------------
Every ``Measurement`` this service emits names the code version that produced it
(ADR-0007 D2). That promise is only worth something if the *model* version is
recorded too — a hectare figure produced by a checkpoint nobody can identify is a
number without provenance wearing the clothes of one.

So a model is registered with the evidence that justifies using it: its held-out
score, the regions it was validated on, and the run that produced it. The registry
refuses to serve a model that cannot supply those.

Degradation is a first-class state
----------------------------------
If no learned model is available — no checkpoint on disk, a corrupt file, torch not
installed — the service does not fail and does not silently return nothing. It
falls back to the deterministic baseline and *says so*, via
``Analysis.degraded_from``. ADR-0007 D7: the two legitimate degraded behaviours are
an abstention with a reason, or a labelled fall back to the baseline. A stored
fixture is neither.

torch is imported lazily, inside the loader. The service must start, answer
``/health`` and serve baseline analyses on a machine with no deep-learning stack —
which is every CI runner, and possibly the demo laptop.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Where checkpoints live. Overridable so a deployment can mount them elsewhere,
#: and so tests can point at a temporary directory rather than the real one.
MODEL_ROOT = Path(os.environ.get("SATQUERY_MODEL_ROOT", "artifacts"))

#: The identifier used when no learned model ran. Not a model name -- it is the
#: absence of one, and it appears in `degraded_from` rather than in `produced_by`.
BASELINE_METHOD = "deterministic-otsu-baseline"


class ModelUnavailable(RuntimeError):
    """No usable learned model. The caller should degrade, not fail."""


@dataclass(frozen=True)
class ModelCard:
    """What is known about a registered model, and how it was measured.

    Every field here exists because a reviewer or a judge can reasonably ask for
    it. ``validation_regions`` in particular: a score means nothing without knowing
    what it was scored on, and this project's scores are region-held-out (see
    ml/training/splits.py), which is the detail that makes them honest.
    """

    name: str
    version: str
    checkpoint: Path
    parameters: int
    validation_iou: float | None
    validation_f1: float | None
    validation_regions: tuple[str, ...]
    train_regions: tuple[str, ...]
    baseline_iou: float | None
    stratified_iou: dict[str, float]

    @property
    def beats_baseline(self) -> bool | None:
        """Whether this model outscored the deterministic baseline on the same split.

        ``None`` when either number is missing. Deliberately not defaulted to
        ``False``: "we did not measure" and "it lost" are different claims, and
        collapsing them is how an unmeasured model gets described as a failed one,
        or worse, the reverse.
        """
        if self.validation_iou is None or self.baseline_iou is None:
            return None
        return self.validation_iou > self.baseline_iou

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "parameters": self.parameters,
            "validation_iou": self.validation_iou,
            "validation_f1": self.validation_f1,
            "validation_regions": list(self.validation_regions),
            "train_regions": list(self.train_regions),
            "baseline_iou": self.baseline_iou,
            "beats_baseline": self.beats_baseline,
            "stratified_iou": self.stratified_iou,
        }


class ModelRegistry:
    """Discovers checkpoints under ``root`` and loads them on demand.

    Discovery is by directory: ``<root>/<name>/best.pt`` with a sibling
    ``metrics.json`` written by ``ml/scripts/train_unet.py``. A checkpoint without
    its metrics is listed but reports no score, and ``beats_baseline`` is ``None``
    rather than an assumption.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else MODEL_ROOT
        self._loaded: dict[str, Any] = {}

    def cards(self) -> tuple[ModelCard, ...]:
        """Every model on disk. Empty is a normal state, not an error."""
        if not self.root.is_dir():
            return ()

        cards: list[ModelCard] = []
        for checkpoint in sorted(self.root.glob("*/best.pt")):
            card = self._read_card(checkpoint)
            if card is not None:
                cards.append(card)
        return tuple(cards)

    def _read_card(self, checkpoint: Path) -> ModelCard | None:
        """Build a card from the metrics file, without loading the weights.

        Reading metadata must not require torch, so this parses the JSON the
        training run wrote rather than opening the checkpoint. Listing the
        available models is something a caller does on a machine that may never
        run inference.
        """
        metrics_path = checkpoint.parent / "metrics.json"
        name = checkpoint.parent.name

        if not metrics_path.is_file():
            logger.warning(
                "model %s has no metrics.json; listing it without a score rather "
                "than assuming one",
                name,
            )
            return ModelCard(
                name=name,
                version="unknown",
                checkpoint=checkpoint,
                parameters=0,
                validation_iou=None,
                validation_f1=None,
                validation_regions=(),
                train_regions=(),
                baseline_iou=None,
                stratified_iou={},
            )

        try:
            metrics = json.loads(metrics_path.read_text())
        except (OSError, json.JSONDecodeError):
            logger.exception("model %s has unreadable metrics.json; skipping", name)
            return None

        model = metrics.get("model", {})
        baseline = metrics.get("baseline", {})
        return ModelCard(
            name=name,
            # Epochs and seed identify the run that produced these weights. Not a
            # hash of the file: two runs with the same config and seed should be
            # recognisable as the same model, and a hash would hide that.
            version=f"e{metrics.get('epochs', '?')}-s{metrics.get('seed', '?')}",
            checkpoint=checkpoint,
            parameters=int(metrics.get("parameters", 0)),
            validation_iou=model.get("iou"),
            validation_f1=model.get("f1"),
            validation_regions=tuple(metrics.get("validation_regions", ())),
            train_regions=tuple(metrics.get("train_regions", ())),
            baseline_iou=baseline.get("iou"),
            stratified_iou=dict(model.get("stratified_iou", {})),
        )

    def load(self, name: str) -> tuple[Any, Any, ModelCard]:
        """Load a model, returning ``(model, normalisation, card)``.

        Raises
        ------
        ModelUnavailable
            If the model is not registered, torch is not installed, or the
            checkpoint cannot be read. The caller degrades to the baseline; it does
            not surface a 500, because a working answer by a labelled weaker method
            is better than no answer.
        """
        if name in self._loaded:
            cached: tuple[Any, Any, ModelCard] = self._loaded[name]
            return cached

        card = next((c for c in self.cards() if c.name == name), None)
        if card is None:
            raise ModelUnavailable(f"no model named {name!r} under {self.root}")

        try:
            import torch  # noqa: PLC0415 -- lazy on purpose; see module docstring

            from ml.models.unet import UNet
            from ml.training.dataset import Normalisation
        except ImportError as error:
            raise ModelUnavailable(
                f"torch is not installed, so {name!r} cannot be loaded "
                "(pip install -r requirements-ml.txt). Falling back to the "
                "deterministic baseline."
            ) from error

        try:
            state = torch.load(card.checkpoint, weights_only=True, map_location="cpu")
            model = UNet(**state["architecture"])
            model.load_state_dict(state["state_dict"])
            model.eval()
            normalisation = Normalisation.from_dict(state["normalisation"])
        except Exception as error:  # noqa: BLE001 -- see comment
            # Deliberately broad. A checkpoint can fail to load in unbounded ways:
            # a truncated file raises UnpicklingError, a partial write raises from
            # zipfile, a torch version mismatch raises RuntimeError, a hand-edited
            # metrics.json raises KeyError. Listing them means being wrong about
            # one and turning a degradable condition into a 500.
            #
            # Every one of them means the same thing operationally -- this model
            # cannot run -- and the answer is always the same: fall back to the
            # baseline and label it. Caught here rather than at the call site so
            # the caller only has to handle ModelUnavailable.
            raise ModelUnavailable(
                f"checkpoint for {name!r} could not be loaded: " f"{type(error).__name__}: {error}"
            ) from error

        loaded: tuple[Any, Any, ModelCard] = (model, normalisation, card)
        self._loaded[name] = loaded
        return loaded

    def default(self) -> str | None:
        """The model to use when the caller does not name one.

        The highest held-out IoU among models that actually beat their baseline.
        A model that lost to the baseline is never selected automatically —
        serving it by default would mean the service quietly does worse than the
        method it was meant to improve on. It stays listed and callable by name,
        because comparing them is the point.
        """
        candidates = [c for c in self.cards() if c.beats_baseline and c.validation_iou is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.validation_iou or 0.0).name
