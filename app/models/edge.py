from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from app.database import Base


class Edge(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), ForeignKey("nodes.name"), nullable=False)
    destination = Column(String(100), ForeignKey("nodes.name"), nullable=False)
    latency = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("source", "destination", name="uq_edge_source_destination"),)
