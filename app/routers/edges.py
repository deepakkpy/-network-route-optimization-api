from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.node import Node
from app.models.edge import Edge
from app.schemas.edge import EdgeCreate, EdgeResponse

router = APIRouter()


@router.post("", response_model=EdgeResponse, status_code=201)
def create_edge(payload: EdgeCreate, db: Session = Depends(get_db)):
    source_node = db.query(Node).filter(Node.name == payload.source).first()
    if not source_node:
        raise HTTPException(status_code=400, detail=f"Source node '{payload.source}' not found")

    dest_node = db.query(Node).filter(Node.name == payload.destination).first()
    if not dest_node:
        raise HTTPException(status_code=400, detail=f"Destination node '{payload.destination}' not found")

    duplicate = db.query(Edge).filter(
        Edge.source == payload.source,
        Edge.destination == payload.destination,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"Edge from '{payload.source}' to '{payload.destination}' already exists",
        )

    edge = Edge(source=payload.source, destination=payload.destination, latency=payload.latency)
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


@router.get("", response_model=list[EdgeResponse])
def list_edges(db: Session = Depends(get_db)):
    return db.query(Edge).all()


@router.delete("/{edge_id}", status_code=204)
def delete_edge(edge_id: int, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == edge_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail=f"Edge with id {edge_id} not found")

    db.delete(edge)
    db.commit()
    return Response(status_code=204)
