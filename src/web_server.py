"""
Transmutator V2 – Web UI server (Fase 5).

Serves the API (scan, config, pipeline control, status) and the static
frontend (Pipboy-Transfer build). Bind to 0.0.0.0 to allow access from other
devices on the LAN.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import (
    get_paths_config,
    get_pipeline_selection,
    get_qbittorrent_config,
    save_paths_config,
    save_pipeline_selection,
    save_qbittorrent_config,
)
from .runtime_pipeline import PipelineRunner

# ---------------------------------------------------------------------------
# Static files path (Pipboy-Transfer build output)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
_STATIC_DIR = _ROOT / "Pipboy-Transfer" / "dist" / "public"
_RUNNER = PipelineRunner()

# ---------------------------------------------------------------------------
# Pydantic models for API
# ---------------------------------------------------------------------------


class PathsConfig(BaseModel):
    torrent_base: Optional[str] = None
    tmp_staging: Optional[str] = None
    output_base: Optional[str] = None
    plex_destination: Optional[str] = None


class QBittorrentConfig(BaseModel):
    enabled: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    api_key_header: Optional[str] = None
    processed_category: Optional[str] = None
    modify_torrent_category: Optional[bool] = None
    categories: Optional[Dict[str, str]] = None


class PipelineSelectionConfig(BaseModel):
    pipeline_selection: Optional[Dict[str, Dict[str, bool]]] = None


class ConfigUpdate(BaseModel):
    paths: Optional[PathsConfig] = None
    qbittorrent: Optional[Dict[str, Any]] = None
    pipeline_selection: Optional[Dict[str, Dict[str, bool]]] = None


class PipelineStartRequest(BaseModel):
    pipeline_selection: Optional[Dict[str, Dict[str, bool]]] = None


class PipelineReorderRequest(BaseModel):
    ordered_ids: list[str]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Transmutator V2 API",
    description="API per al pipeline ETL i la Web UI Pip-Boy.",
    version="0.9.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get("/api/config")
def api_get_config() -> Dict[str, Any]:
    """Return full config for the Web UI (paths, qbittorrent, pipeline_selection)."""
    paths = get_paths_config()
    qbt = get_qbittorrent_config()
    pipeline_selection = get_pipeline_selection()
    return {
        "paths": paths,
        "qbittorrent": {
            "enabled": qbt["enabled"],
            "host": qbt["host"],
            "port": qbt["port"],
            "url": qbt["url"],
            "username": qbt["username"],
            "password": qbt["password"],
            "api_key": qbt["api_key"],
            "api_key_header": qbt["api_key_header"],
            "processed_category": qbt["processed_category"],
            "modify_torrent_category": qbt["modify_torrent_category"],
            "categories": qbt["categories"],
        },
        "pipeline_selection": pipeline_selection,
    }


@app.put("/api/config")
def api_put_config(body: ConfigUpdate) -> Dict[str, str]:
    """Update config (paths, qbittorrent, pipeline_selection). Partial updates supported."""
    if body.paths is not None:
        save_paths_config(body.paths.model_dump(exclude_none=True))
    if body.qbittorrent is not None:
        save_qbittorrent_config(body.qbittorrent)
    if body.pipeline_selection is not None:
        save_pipeline_selection(body.pipeline_selection)
    return {"status": "ok"}


@app.post("/api/qbittorrent/test")
def api_qbittorrent_test(body: Optional[QBittorrentConfig] = None) -> Dict[str, Any]:
    """Test qBittorrent connectivity with provided or saved settings."""
    cfg = get_qbittorrent_config()
    payload = body.model_dump(exclude_none=True) if body is not None else {}
    merged = {**cfg, **payload}
    host = str(merged.get("host") or "").strip() or "http://localhost"
    raw_port = merged.get("port", 8080)
    try:
        port = int(raw_port or 8080)
    except (TypeError, ValueError):
        port = 8080
    url = str(merged.get("url") or f"{host.rstrip('/')}:{port}")

    from .qbittorrent import QBittorrentClient

    client = QBittorrentClient(
        url=url,
        username=merged.get("username"),
        password=merged.get("password"),
        api_key=merged.get("api_key"),
        api_key_header=merged.get("api_key_header"),
    )
    return client.test_connection()


@app.post("/api/scan")
def api_scan() -> Dict[str, Any]:
    """Run file scan (TMP + torrent sources) and return list of files."""
    files = _RUNNER.scan()
    return {"files": files, "count": len(files)}


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    """Return pipeline status and last scan result."""
    return _RUNNER.snapshot()


@app.get("/api/report/latest")
def api_report_latest() -> Dict[str, Any]:
    """Return the latest persisted report, if any."""
    payload = _RUNNER.latest_report_payload()
    if payload is None:
        raise HTTPException(status_code=404, detail="No report available")
    return payload


@app.get("/api/report/history")
def api_report_history(limit: int = 20) -> Dict[str, Any]:
    """Return compact metadata for persisted reports."""
    safe_limit = max(1, min(limit, 100))
    return {"reports": _RUNNER.report_history(limit=safe_limit)}


@app.get("/api/report/{report_id}")
def api_report_by_id(report_id: str) -> Dict[str, Any]:
    """Return a persisted report by id."""
    payload = _RUNNER.report_payload(report_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return payload


@app.post("/api/pipeline/start")
def api_pipeline_start(body: Optional[PipelineStartRequest] = None) -> Dict[str, Any]:
    """Start the pipeline in background."""
    selection = None
    if body is not None and body.pipeline_selection is not None:
        selection = body.pipeline_selection
    if not _RUNNER.start(selection=selection):
        raise HTTPException(status_code=409, detail="Pipeline already running")
    return _RUNNER.snapshot()


@app.post("/api/pipeline/stop")
def api_pipeline_stop() -> Dict[str, Any]:
    """Request immediate stop of the running pipeline."""
    if not _RUNNER.stop():
        raise HTTPException(status_code=409, detail="No running pipeline")
    return _RUNNER.snapshot()


@app.post("/api/pipeline/pause")
def api_pipeline_pause() -> Dict[str, Any]:
    """Pause the currently running subprocess, if any."""
    if not _RUNNER.pause():
        raise HTTPException(status_code=409, detail="Pipeline is not running")
    return _RUNNER.snapshot()


@app.post("/api/pipeline/resume")
def api_pipeline_resume() -> Dict[str, Any]:
    """Resume a paused pipeline."""
    if not _RUNNER.resume():
        raise HTTPException(status_code=409, detail="Pipeline is not paused")
    return _RUNNER.snapshot()


@app.post("/api/pipeline/reorder")
def api_pipeline_reorder(body: PipelineReorderRequest) -> Dict[str, Any]:
    """Reorder pending transform items."""
    return _RUNNER.reorder_transform_queue(body.ordered_ids)


# ---------------------------------------------------------------------------
# Static SPA (fallback for SPA routing)
# ---------------------------------------------------------------------------


def _serve_static(path: str) -> FileResponse:
    """Serve static file; for SPA, return index.html for non-file paths."""
    if path and path != "index.html":
        file_path = _STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
    index_path = _STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Static files not found. Build the client: cd Pipboy-Transfer && npm run build")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    """Serve the SPA: static assets or index.html for client-side routes."""
    return _serve_static(full_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_server(host: str = "0.0.0.0", port: Optional[int] = None) -> None:
    import uvicorn
    if port is None:
        port = int(os.environ.get("TRANSMUTATOR_PORT", "1312"))
    uvicorn.run(
        "src.web_server:app",
        host=host,
        port=port,
        reload=os.environ.get("TRANSMUTATOR_DEV") == "1",
    )


if __name__ == "__main__":
    run_server()
