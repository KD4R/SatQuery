import logging
import json
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FixtureFallbackManager:
    """
    Implements P4-17: Geo failure recovery and fixture fallback.
    Provides deterministic graceful degradation when live STAC APIs or
    inference services timeout, utilizing the 'tests/recorded/' pinned fixtures.
    """

    def __init__(self, fixture_dir: str = "tests/recorded"):
        self.fixture_dir = fixture_dir

    def recover_search(self, fallback_id: str) -> Dict[str, Any]:
        """
        Retrieves recorded STAC search JSON when live APIs fail.
        """
        logger.warning(f"Live API failure. Falling back to recorded fixture: {fallback_id}")
        fixture_path = os.path.join(self.fixture_dir, f"{fallback_id}.json")

        if not os.path.exists(fixture_path):
            raise FileNotFoundError(f"Fallback fixture not found: {fixture_path}")

        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore

    def recover_asset(self, fallback_id: str) -> str:
        """
        Retrieves a local recorded COG or raster when asset download fails.
        """
        logger.warning(f"Asset retrieval failed. Falling back to local pinned asset: {fallback_id}")
        fixture_path = os.path.join(self.fixture_dir, f"{fallback_id}.tif")

        if not os.path.exists(fixture_path):
            raise FileNotFoundError(f"Fallback raster not found: {fixture_path}")

        return fixture_path


fixture_fallback = FixtureFallbackManager()
