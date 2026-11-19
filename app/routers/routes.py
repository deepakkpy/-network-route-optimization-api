from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.node import Node
from app.models.route_history import RouteHistory
from app.schemas.route import RouteRequest, RouteResponse, RouteHistoryResponse
from app.services import graph_service

router = APIRouter()


@router.post("/shortest", response_model=RouteResponse)
def get_shortest_route(payload: RouteRequest, db: Session = Depends(get_db)):
    source = payload.source.strip()
    destination = payload.destination.strip()

    source_node = db.query(Node).filter(Node.name == source).first()
    if not source_node:
        raise HTTPException(status_code=400, detail=f"Source node '{source}' not found")

    dest_node = db.query(Node).filter(Node.name == destination).first()
    if not dest_node:
        raise HTTPException(status_code=400, detail=f"Destination node '{destination}' not found")

    result = graph_service.find_shortest_path(source, destination, db)

    if not result["found"]:
        return JSONResponse(
            status_code=404,
            content={"error": f"No path exists between {source} and {destination}"},
        )

    history = RouteHistory(
        source=source,
        destination=destination,
        total_latency=result["total_latency"],
        path=result["path"],
    )
    db.add(history)
    db.commit()

    return RouteResponse(total_latency=result["total_latency"], path=result["path"])


@router.get("/history", response_model=list[RouteHistoryResponse])
def get_route_history(
    source: Optional[str] = None,
    destination: Optional[str] = None,
    limit: Optional[int] = Query(None, ge=1),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    query = db.query(RouteHistory)

    if source is not None:
        query = query.filter(RouteHistory.source == source.strip())
    if destination is not None:
        query = query.filter(RouteHistory.destination == destination.strip())
    if date_from is not None:
        query = query.filter(RouteHistory.created_at >= date_from)
    if date_to is not None:
        query = query.filter(RouteHistory.created_at <= date_to)

    query = query.order_by(RouteHistory.created_at.desc())

    if limit is not None:
        query = query.limit(limit)

    return query.all()
