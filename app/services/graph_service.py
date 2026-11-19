import networkx as nx
from sqlalchemy.orm import Session
from app.models.edge import Edge


def find_shortest_path(source: str, destination: str, db: Session) -> dict:
    if source == destination:
        return {"path": [source], "total_latency": 0.0, "found": True}

    edges = db.query(Edge).all()

    G = nx.DiGraph()
    for edge in edges:
        G.add_edge(edge.source, edge.destination, latency=edge.latency)

    try:
        path = nx.dijkstra_path(G, source, destination, weight="latency")
        total = nx.dijkstra_path_length(G, source, destination, weight="latency")
        return {"path": path, "total_latency": round(total, 2), "found": True}
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"path": None, "total_latency": None, "found": False}
