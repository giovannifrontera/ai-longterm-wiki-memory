"""Wiki frontend server — FastAPI + WebSocket + file watcher + JWT auth."""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

sys.path.insert(0, str(Path(__file__).parent))
import wiki_graph  # noqa: E402

_workspace: str = ""
_cfg: dict = {}
_no_auth: bool = False
_secret_key: str = ""
_jwt_secret: str = ""  # derived at configure() — kept separate from login password
_session_days: int = 7

_ws_clients: Set[WebSocket] = set()

app = FastAPI(docs_url=None, redoc_url=None)


def configure(workspace: str, cfg: dict, no_auth: bool) -> None:
    global _workspace, _cfg, _no_auth, _secret_key, _jwt_secret, _session_days
    import hmac
    _workspace = workspace
    _cfg = cfg
    _no_auth = no_auth
    frontend = cfg.get("frontend", {})
    _secret_key = os.environ.get("WIKI_PASSWORD") or frontend.get("password", "changeme")
    # Derive a separate JWT signing secret so it is never the raw login password.
    _jwt_secret = hmac.digest(_secret_key.encode(), b"wiki-jwt-v1", "sha256").hex()
    _session_days = int(frontend.get("session_days", 7))


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _no_auth:
            return await call_next(request)
        if request.url.path.startswith("/auth/"):
            return await call_next(request)
        token = request.cookies.get("wiki_session")
        if not token or not _verify_token(token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthMiddleware)


def _make_token() -> str:
    from jose import jwt
    exp = datetime.now(timezone.utc) + timedelta(days=_session_days)
    return jwt.encode({"exp": exp}, _jwt_secret, algorithm="HS256")


def _verify_token(token: str) -> bool:
    from jose import jwt, JWTError
    try:
        jwt.decode(token, _jwt_secret, algorithms=["HS256"])
        return True
    except JWTError:
        return False


@app.post("/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_body"}, status_code=400)
    if body.get("password") != _secret_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    token = _make_token()
    resp = JSONResponse({"status": "ok"})
    resp.set_cookie(
        "wiki_session", token, httponly=True, samesite="lax",
        max_age=_session_days * 86400,
    )
    return resp


@app.post("/auth/logout")
async def logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("wiki_session")
    return resp


@app.get("/api/graph")
async def api_graph():
    data = wiki_graph.build_graph(_workspace, _cfg)
    return JSONResponse(data)


@app.get("/api/page/{path:path}")
async def api_page(path: str):
    detail = wiki_graph.get_page_detail(_workspace, path, _cfg)
    if detail is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(detail)


@app.get("/")
async def index():
    html_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    if not _no_auth:
        token = websocket.cookies.get("wiki_session")
        if not token or not _verify_token(token):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


async def _broadcast(message: dict) -> None:
    dead: Set[WebSocket] = set()
    payload = json.dumps(message)
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_file_watcher())
    asyncio.create_task(_query_log_watcher())


async def _file_watcher():
    try:
        from watchfiles import awatch
    except ImportError:
        return
    import wiki_graph
    ws = Path(_workspace)
    watch_dirs = [str(d) for d in (ws / "wiki", ws / "wiki-works") if d.exists()]
    if not watch_dirs:
        return
    async for _changes in awatch(*watch_dirs):
        wiki_graph.mark_dirty()
        await _broadcast({"type": "graph_update"})


async def _query_log_watcher():
    log_path = Path(_workspace) / ".wiki-query-log.jsonl"
    pos = log_path.stat().st_size if log_path.exists() else 0
    while True:
        await asyncio.sleep(0.5)
        if not log_path.exists():
            continue
        size = log_path.stat().st_size
        if size <= pos:
            continue
        with open(log_path, encoding="utf-8") as f:
            f.seek(pos)
            new_content = f.read()
            pos = f.tell()  # use actual read position — avoids skipping bytes if file grew during read
        for line in new_content.splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                paths = entry.get("paths", [])
                if paths:
                    await _broadcast({"type": "query_hit", "paths": paths})
            except json.JSONDecodeError:
                pass
