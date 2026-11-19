from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RouteRequest(BaseModel):
    source: str
    destination: str


class RouteResponse(BaseModel):
    total_latency: float
    path: list[str]


class RouteHistoryResponse(BaseModel):
    id: int
    source: str
    destination: str
    total_latency: float | None
    path: list[str] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
