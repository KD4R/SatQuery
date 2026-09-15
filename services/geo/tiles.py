import logging
from fastapi import APIRouter

from titiler.core.factory import TilerFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tiles", tags=["tiles"])

# Implements P4-15: TiTiler integration
# Embedding titiler within the analysis service boundary for dynamic COG delivery
cog_tiler = TilerFactory()

# Mount titiler routes
router.include_router(cog_tiler.router)
