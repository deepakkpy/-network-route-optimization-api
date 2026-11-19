from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.node import Node
from app.models.edge import Edge
from app.schemas.node import NodeCreate, NodeResponse

router = APIRouter()


@router.post("", response_model=NodeResponse, status_code=201)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)):
    if not payload.name:
        raise HTTPException(status_code=400, detail="Name is required")

    existing = db.query(Node).filter(Node.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Node '{payload.name}' already exists")

    node = Node(name=payload.name)
    db.add(node)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Node '{payload.name}' already exists")
    db.refresh(node)
    return node


@router.get("", response_model=list[NodeResponse])
def list_nodes(db: Session = Depends(get_db)):
    return db.query(Node).all()


@router.delete("/{node_id}", status_code=204)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail=f"Node with id {node_id} not found")

    db.query(Edge).filter(
        (Edge.source == node.name) | (Edge.destination == node.name)
    ).delete(synchronize_session=False)

    db.delete(node)
    db.commit()
    return Response(status_code=204)
