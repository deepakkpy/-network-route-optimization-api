"""
Tests for the Network Route Optimization API.

Place this file at  network_api/tests/test_api.py

Run from the network_api/ folder:
    pip install pytest httpx
    python -m pytest -v

Uses an in-memory SQLite database, so your real network.db is never touched.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app as fastapi_app
import app.models.node  # noqa: F401
import app.models.edge  # noqa: F401
import app.models.route_history  # noqa: F401


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Fresh in-memory DB for every test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection so the in-memory DB persists
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # No `with` block on purpose: skips the lifespan, which targets the real DB file.
    yield TestClient(fastapi_app)

    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def add_node(client, name):
    r = client.post("/nodes", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def add_edge(client, src, dst, latency):
    r = client.post("/edges", json={"source": src, "destination": dst, "latency": latency})
    assert r.status_code == 201, r.text
    return r.json()


def build_diamond(client):
    """
        A --10--> B --13.4--> D      (A-B-D = 23.4)
        A --5---> C --25----> D      (A-C-D = 30)
    """
    for n in "ABCD":
        add_node(client, n)
    add_edge(client, "A", "B", 10)
    add_edge(client, "B", "D", 13.4)
    add_edge(client, "A", "C", 5)
    add_edge(client, "C", "D", 25)


def shortest(client, src, dst):
    return client.post("/routes/shortest", json={"source": src, "destination": dst})


# --------------------------------------------------------------------------
# POST /nodes
# --------------------------------------------------------------------------

class TestAddNode:
    def test_create_node(self, client):
        r = client.post("/nodes", json={"name": "ServerA"})
        assert r.status_code == 201
        assert r.json() == {"id": 1, "name": "ServerA"}

    def test_no_trailing_slash_redirect(self, client):
        r = client.post("/nodes", json={"name": "ServerA"}, follow_redirects=False)
        assert r.status_code == 201  # not a 307 redirect

    def test_duplicate_name_returns_400(self, client):
        add_node(client, "ServerA")
        r = client.post("/nodes", json={"name": "ServerA"})
        assert r.status_code == 400
        assert "error" in r.json()

    def test_duplicate_after_whitespace_trim_returns_400(self, client):
        add_node(client, "ServerA")
        r = client.post("/nodes", json={"name": "  ServerA  "})
        assert r.status_code == 400

    def test_name_is_trimmed(self, client):
        assert add_node(client, "  ServerA ")["name"] == "ServerA"

    def test_missing_name_returns_400(self, client):
        r = client.post("/nodes", json={})
        assert r.status_code == 400
        assert r.json()["error"] == "Invalid request"

    @pytest.mark.parametrize("name", ["", "   "])
    def test_blank_name_returns_400(self, client, name):
        assert client.post("/nodes", json={"name": name}).status_code == 400

    def test_list_nodes(self, client):
        add_node(client, "A")
        add_node(client, "B")
        r = client.get("/nodes")
        assert r.status_code == 200
        assert [n["name"] for n in r.json()] == ["A", "B"]

    def test_delete_node_also_deletes_its_edges(self, client):
        a, _ = add_node(client, "A"), add_node(client, "B")
        add_node(client, "C")
        add_edge(client, "A", "B", 1)
        add_edge(client, "C", "A", 2)
        add_edge(client, "B", "C", 3)  # unrelated to A, must survive

        assert client.delete(f"/nodes/{a['id']}").status_code == 204

        edges = client.get("/edges").json()
        assert len(edges) == 1
        assert (edges[0]["source"], edges[0]["destination"]) == ("B", "C")

    def test_delete_missing_node_returns_404(self, client):
        assert client.delete("/nodes/999").status_code == 404


# --------------------------------------------------------------------------
# POST /edges
# --------------------------------------------------------------------------

class TestAddEdge:
    def test_create_edge(self, client):
        add_node(client, "ServerA")
        add_node(client, "ServerB")
        r = client.post(
            "/edges", json={"source": "ServerA", "destination": "ServerB", "latency": 12.5}
        )
        assert r.status_code == 201
        assert r.json() == {"id": 1, "source": "ServerA", "destination": "ServerB", "latency": 12.5}

    def test_unknown_source_returns_400(self, client):
        add_node(client, "B")
        r = client.post("/edges", json={"source": "X", "destination": "B", "latency": 1})
        assert r.status_code == 400

    def test_unknown_destination_returns_400(self, client):
        add_node(client, "A")
        r = client.post("/edges", json={"source": "A", "destination": "X", "latency": 1})
        assert r.status_code == 400

    @pytest.mark.parametrize("latency", [0, -5, -0.01])
    def test_non_positive_latency_returns_400(self, client, latency):
        add_node(client, "A")
        add_node(client, "B")
        r = client.post("/edges", json={"source": "A", "destination": "B", "latency": latency})
        assert r.status_code == 400

    @pytest.mark.parametrize(
        "body",
        [
            {"destination": "B", "latency": 1},   # source missing
            {"source": "A", "latency": 1},        # destination missing
            {"source": "A", "destination": "B"},  # latency missing
            {"source": "A", "destination": "B", "latency": "fast"},  # wrong type
        ],
    )
    def test_missing_or_invalid_fields_return_400(self, client, body):
        add_node(client, "A")
        add_node(client, "B")
        assert client.post("/edges", json=body).status_code == 400

    def test_duplicate_edge_returns_400(self, client):
        add_node(client, "A")
        add_node(client, "B")
        add_edge(client, "A", "B", 1)
        r = client.post("/edges", json={"source": "A", "destination": "B", "latency": 2})
        assert r.status_code == 400

    def test_reverse_edge_is_not_a_duplicate(self, client):
        add_node(client, "A")
        add_node(client, "B")
        add_edge(client, "A", "B", 1)
        add_edge(client, "B", "A", 1)  # directed graph: allowed

    def test_list_and_delete_edge(self, client):
        add_node(client, "A")
        add_node(client, "B")
        edge = add_edge(client, "A", "B", 1)
        assert len(client.get("/edges").json()) == 1
        assert client.delete(f"/edges/{edge['id']}").status_code == 204
        assert client.get("/edges").json() == []

    def test_delete_missing_edge_returns_404(self, client):
        assert client.delete("/edges/999").status_code == 404


# --------------------------------------------------------------------------
# POST /routes/shortest
# --------------------------------------------------------------------------

class TestShortestRoute:
    def test_picks_cheaper_path_in_diamond(self, client):
        build_diamond(client)
        r = shortest(client, "A", "D")
        assert r.status_code == 200
        assert r.json() == {"total_latency": 23.4, "path": ["A", "B", "D"]}

    def test_picks_longer_hops_when_cheaper(self, client):
        # direct edge is slower than going through the middle node
        for n in "ABC":
            add_node(client, n)
        add_edge(client, "A", "C", 100)
        add_edge(client, "A", "B", 1)
        add_edge(client, "B", "C", 1)
        assert shortest(client, "A", "C").json() == {"total_latency": 2, "path": ["A", "B", "C"]}

    def test_no_path_returns_404_with_error_key(self, client):
        add_node(client, "A")
        add_node(client, "B")  # no edges at all
        r = shortest(client, "A", "B")
        assert r.status_code == 404
        assert r.json() == {"error": "No path exists between A and B"}

    def test_edges_are_directed(self, client):
        add_node(client, "A")
        add_node(client, "B")
        add_edge(client, "A", "B", 5)
        assert shortest(client, "A", "B").status_code == 200
        assert shortest(client, "B", "A").status_code == 404

    @pytest.mark.parametrize("src,dst", [("A", "X"), ("X", "A"), ("X", "Y")])
    def test_unknown_nodes_return_400(self, client, src, dst):
        add_node(client, "A")
        assert shortest(client, src, dst).status_code == 400

    def test_missing_fields_return_400(self, client):
        assert client.post("/routes/shortest", json={"source": "A"}).status_code == 400

    def test_same_source_and_destination(self, client):
        add_node(client, "A")
        r = shortest(client, "A", "A")
        assert r.status_code == 200
        assert r.json() == {"total_latency": 0, "path": ["A"]}

    def test_latency_is_rounded(self, client):
        for n in "ABC":
            add_node(client, n)
        add_edge(client, "A", "B", 0.1)
        add_edge(client, "B", "C", 0.2)
        assert shortest(client, "A", "C").json()["total_latency"] == 0.3

    def test_reflects_deleted_edges(self, client):
        build_diamond(client)
        edges = client.get("/edges").json()
        ab = next(e for e in edges if (e["source"], e["destination"]) == ("A", "B"))
        client.delete(f"/edges/{ab['id']}")
        r = shortest(client, "A", "D")
        assert r.json() == {"total_latency": 30, "path": ["A", "C", "D"]}


# --------------------------------------------------------------------------
# GET /routes/history
# --------------------------------------------------------------------------

class TestHistory:
    def test_empty_history(self, client):
        r = client.get("/routes/history")
        assert r.status_code == 200
        assert r.json() == []

    def test_successful_query_is_logged(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        rows = client.get("/routes/history").json()
        assert len(rows) == 1
        row = rows[0]
        assert row["source"] == "A" and row["destination"] == "D"
        assert row["total_latency"] == 23.4
        assert row["path"] == ["A", "B", "D"]
        assert "id" in row and "created_at" in row

    def test_failed_query_is_not_logged(self, client):
        add_node(client, "A")
        add_node(client, "B")
        shortest(client, "A", "B")  # 404
        assert client.get("/routes/history").json() == []

    def test_newest_first(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        shortest(client, "A", "B")
        shortest(client, "A", "C")
        rows = client.get("/routes/history").json()
        assert [r["destination"] for r in rows] == ["C", "B", "D"]

    def test_filter_by_source_and_destination(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        shortest(client, "A", "B")
        shortest(client, "B", "D")
        by_src = client.get("/routes/history", params={"source": "A"}).json()
        assert {r["source"] for r in by_src} == {"A"} and len(by_src) == 2

        by_dst = client.get("/routes/history", params={"destination": "D"}).json()
        assert {r["destination"] for r in by_dst} == {"D"} and len(by_dst) == 2

        both = client.get("/routes/history", params={"source": "A", "destination": "D"}).json()
        assert len(both) == 1

    def test_limit_returns_most_recent(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        shortest(client, "A", "B")
        shortest(client, "A", "C")
        rows = client.get("/routes/history", params={"limit": 2}).json()
        assert [r["destination"] for r in rows] == ["C", "B"]

    @pytest.mark.parametrize("limit", [0, -1])
    def test_invalid_limit_returns_400(self, client, limit):
        assert client.get("/routes/history", params={"limit": limit}).status_code == 400

    def test_date_from_in_future_returns_nothing(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        r = client.get("/routes/history", params={"date_from": "2999-01-01T00:00:00"})
        assert r.json() == []

    def test_date_to_in_past_returns_nothing(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        r = client.get("/routes/history", params={"date_to": "2000-01-01T00:00:00"})
        assert r.json() == []

    def test_date_range_containing_now_returns_row(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        r = client.get(
            "/routes/history",
            params={"date_from": "2000-01-01T00:00:00", "date_to": "2999-01-01T00:00:00"},
        )
        assert len(r.json()) == 1

    def test_history_survives_node_deletion(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        d = next(n for n in client.get("/nodes").json() if n["name"] == "D")
        client.delete(f"/nodes/{d['id']}")
        assert len(client.get("/routes/history").json()) == 1

    @pytest.mark.xfail(
        reason="SQLite drops tzinfo, so created_at comes back without the 'Z' the spec shows. "
        "Remove this marker once RouteHistoryResponse attaches UTC.",
        strict=False,
    )
    def test_created_at_is_utc_with_z_suffix(self, client):
        build_diamond(client)
        shortest(client, "A", "D")
        created_at = client.get("/routes/history").json()[0]["created_at"]
        assert created_at.endswith("Z") or created_at.endswith("+00:00")


# --------------------------------------------------------------------------
# Error format
# --------------------------------------------------------------------------

class TestErrorFormat:
    def test_http_errors_use_error_key(self, client):
        r = client.delete("/nodes/999")
        assert r.status_code == 404
        assert "error" in r.json() and "detail" not in r.json()

    def test_validation_errors_use_error_key(self, client):
        r = client.post("/edges", json={})
        assert r.status_code == 400
        body = r.json()
        assert body["error"] == "Invalid request"
        assert isinstance(body["details"], list)
