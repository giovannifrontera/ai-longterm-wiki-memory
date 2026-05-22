import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _make_page(path: Path, title: str, body: str = "Content.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\n---\n\n{body}", encoding="utf-8")


@pytest.fixture
def server_client(tmp_workspace):
    import wiki_graph
    wiki_graph._CACHE = None
    wiki_graph._CACHE_TIME = 0.0
    wiki_graph._DIRTY = False
    _make_page(tmp_workspace / "wiki" / "concepts" / "rag.md", "RAG")

    import wiki_server
    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    wiki_server.configure(str(tmp_workspace), cfg, no_auth=True)

    from fastapi.testclient import TestClient
    return TestClient(wiki_server.app)


@pytest.fixture
def auth_client(tmp_workspace):
    import wiki_graph
    wiki_graph._CACHE = None

    import wiki_server
    cfg = json.loads((tmp_workspace / "wiki.config.json").read_text())
    cfg.setdefault("frontend", {})["password"] = "testpass"
    wiki_server.configure(str(tmp_workspace), cfg, no_auth=False)

    from fastapi.testclient import TestClient
    return TestClient(wiki_server.app, raise_server_exceptions=True)


def test_api_graph_endpoint(server_client):
    resp = server_client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert any(n["id"] == "wiki/concepts/rag" for n in data["nodes"])


def test_api_page_endpoint(server_client, tmp_workspace):
    resp = server_client.get("/api/page/wiki/concepts/rag.md")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "RAG" in data["content"]
    assert "metadata" in data


def test_api_page_not_found(server_client):
    resp = server_client.get("/api/page/wiki/concepts/nonexistent.md")
    assert resp.status_code == 404


def test_auth_required(auth_client):
    resp = auth_client.get("/api/graph", cookies={})
    assert resp.status_code == 401


def test_auth_login(auth_client):
    resp = auth_client.post("/auth/login", json={"password": "testpass"})
    assert resp.status_code == 200
    assert "wiki_session" in resp.cookies


def test_auth_wrong_password(auth_client):
    resp = auth_client.post("/auth/login", json={"password": "wrongpass"})
    assert resp.status_code == 401


def test_auth_cookie_grants_access(auth_client):
    login = auth_client.post("/auth/login", json={"password": "testpass"})
    assert login.status_code == 200
    token = login.cookies["wiki_session"]
    resp = auth_client.get("/api/graph", cookies={"wiki_session": token})
    assert resp.status_code == 200


def test_auth_logout(auth_client):
    login = auth_client.post("/auth/login", json={"password": "testpass"})
    token = login.cookies["wiki_session"]
    logout = auth_client.post("/auth/logout", cookies={"wiki_session": token})
    assert logout.status_code == 200


def test_websocket_connects_no_auth(server_client):
    import wiki_server
    with server_client.websocket_connect("/ws") as ws:
        assert len(wiki_server._ws_clients) == 1


def test_websocket_auth_rejected_without_cookie(auth_client):
    try:
        with auth_client.websocket_connect("/ws", cookies={}) as ws:
            ws.receive_text()
        rejected = False
    except Exception:
        rejected = True
    assert rejected, "Expected WebSocket to be rejected without valid cookie"
