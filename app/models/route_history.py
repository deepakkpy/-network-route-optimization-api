from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.database import Base


class RouteHistory(Base):
    __tablename__ = "route_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    total_latency = Column(Float, nullable=True)
    path = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
