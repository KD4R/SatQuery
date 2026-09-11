from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

app = FastAPI(
    title="SatQuery AI - API Gateway",
    description="Gateway service routing and orchestrating all external browser calls.",
    version="1.0.0",
)

router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="gateway")


app.include_router(router)
