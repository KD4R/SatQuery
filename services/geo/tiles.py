import logging
from fastapi import APIRouter

try:
    from titiler.core.factory import TilerFactory
    from titiler.core.errors import TilerError
except ImportError:
    # Handle environment without titiler installed yet
    TilerFactory = None
    TilerError = Exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tiles", tags=["tiles"])

if TilerFactory:
    # Implements P4-15: TiTiler integration
    # Embedding titiler within the analysis service boundary for dynamic COG delivery
    cog_tiler = TilerFactory()

    # Mount titiler routes
    router.include_router(cog_tiler.router)
else:
    logger.warning("TiTiler not installed. Tile endpoints will be unavailable.")

    @router.get("/{z}/{x}/{y}")
    def tile_stub(z: int, x: int, y: int):
        return {"error": "TiTiler integration active but package missing"}
