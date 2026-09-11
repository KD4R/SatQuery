from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

app = FastAPI(
    title="SatQuery AI - Mission Service",
    description="Service handling Mission and AOI lifecycles.",
    version="1.0.0",
)

router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="mission")


app.include_router(router)
