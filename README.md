# Network Route Optimization API

A REST API built with **FastAPI**, **SQLAlchemy**, and **NetworkX** that models a network of servers as a directed weighted graph and finds the shortest (lowest-latency) path between any two nodes using Dijkstra's algorithm.

---

## Stack

| Component | Purpose |
|-----------|---------|
| FastAPI | HTTP framework and automatic OpenAPI docs |
| SQLAlchemy (sync) | ORM for SQLite persistence |
| NetworkX | Graph construction and Dijkstra shortest-path |
| Pydantic v2 | Request/response validation |
| Uvicorn | ASGI server |

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. The .env file is already included with SQLite config
#    DATABASE_URL=sqlite:///./network.db
```

---

## Running the API

Run this command from inside the `network_api/` directory:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

---

## Endpoints

### Nodes

#### POST /nodes — Add a node
```bash
curl -X POST http://localhost:8000/nodes \
  -H "Content-Type: application/json" \
  -d '{"name": "ServerA"}'
```
Response `201`:
```json
{"id": 1, "name": "ServerA"}
```

#### GET /nodes — List all nodes
```bash
curl http://localhost:8000/nodes
```
Response `200`:
```json
[{"id": 1, "name": "ServerA"}, {"id": 2, "name": "ServerB"}]
```

#### DELETE /nodes/{id} — Delete a node (also removes connected edges)
```bash
curl -X DELETE http://localhost:8000/nodes/1
```
Response `204 No Content`

---

### Edges

#### POST /edges — Add an edge
```bash
curl -X POST http://localhost:8000/edges \
  -H "Content-Type: application/json" \
  -d '{"source": "ServerA", "destination": "ServerB", "latency": 12.5}'
```
Response `201`:
```json
{"id": 1, "source": "ServerA", "destination": "ServerB", "latency": 12.5}
```

#### GET /edges — List all edges
```bash
curl http://localhost:8000/edges
```
Response `200`:
```json
[{"id": 1, "source": "ServerA", "destination": "ServerB", "latency": 12.5}]
```

#### DELETE /edges/{id} — Delete an edge
```bash
curl -X DELETE http://localhost:8000/edges/1
```
Response `204 No Content`

---

### Routes

#### POST /routes/shortest — Find the shortest path
```bash
curl -X POST http://localhost:8000/routes/shortest \
  -H "Content-Type: application/json" \
  -d '{"source": "ServerA", "destination": "ServerD"}'
```
Response `200` (path found):
```json
{"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]}
```
Response `404` (no path):
```json
{"error": "No path exists between ServerA and ServerD"}
```

#### GET /routes/history — Query route history
```bash
# All history
curl http://localhost:8000/routes/history

# Filter by source and limit results
curl "http://localhost:8000/routes/history?source=ServerA&limit=5"

# Filter by date range
curl "http://localhost:8000/routes/history?date_from=2026-01-01T00:00:00&date_to=2026-12-31T23:59:59"
```
Response `200`:
```json
[
  {
    "id": 1,
    "source": "ServerA",
    "destination": "ServerD",
    "total_latency": 23.4,
    "path": ["ServerA", "ServerB", "ServerD"],
    "created_at": "2026-02-20T14:32:00Z"
  }
]
```

---

## Graph Algorithm

Each call to `POST /routes/shortest` rebuilds a directed weighted graph from all edges stored in the database, then runs **Dijkstra's algorithm** (via `networkx.dijkstra_path` and `networkx.dijkstra_path_length`) with edge latency as the weight. This guarantees the minimum-latency path is returned. The graph is not cached — it is always reconstructed from the current DB state so topology changes are reflected immediately.

---

## Error Reference

| Code | Meaning |
|------|---------|
| 400 | Invalid input — missing fields, latency ≤ 0, NaN/inf latency, duplicate node/edge, unknown node name. Validation errors return `{"error": "Invalid request", "details": [...]}` |
| 404 | Resource not found, or no path exists between the given nodes |
| 204 | Successful deletion (no response body) |
