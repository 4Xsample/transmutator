"""
Runtime pipeline helpers for the Web UI and other non-TUI entry points.

This module centralizes:
- scan rows shown by the API
- mutable runtime state for a background pipeline execution
- start / stop / pause / resume controls backed by ProcessHandle
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import Config, get_pipeline_selection
from .converter import ConversionResult, MediaConverter, ProcessHandle
from .file_detector import FileDetector, MediaFile
from .pipeline import ExtractPhase, LoadPhase
from .qbittorrent import QBittorrentClient
from .report import ReportData, list_reports, load_report_json, save_report, save_report_json


def scan_pipeline_files() -> List[Dict[str, Any]]:
    """Scan TMP and torrent sources and return API-friendly file rows."""
    tmp_by_cat = FileDetector.scan_all_categories()
    tmp_keys: set[tuple[str, str]] = set()
    all_media: List[MediaFile] = []

    for cat, files in tmp_by_cat.items():
        for media in files:
            all_media.append(media)
            try:
                rel = str(media.path.relative_to(Config.get_tmp_path(cat)))
            except ValueError:
                rel = media.path.name
            tmp_keys.add((cat, rel))

    rows: List[Dict[str, Any]] = []

    if Config.TORRENT_BASE.exists():
        try:
            tor_by_cat = FileDetector.scan_torrent_sources()
        except Exception:
            tor_by_cat = {}
        for cat, files in tor_by_cat.items():
            for media in files:
                try:
                    rel = str(media.path.relative_to(Config.get_torrent_path(cat)))
                except ValueError:
                    rel = media.path.name
                already = (cat, rel) in tmp_keys
                rows.append(
                    {
                        "id": f"{cat}:{rel}",
                        "path": str(media.path),
                        "name": media.path.name,
                        "category": cat,
                        "status": "done" if already else "pending",
                        "progress": 100.0 if already else 0.0,
                    }
                )

    if not rows:
        for media in all_media:
            rows.append(
                {
                    "id": f"{media.category}:{media.path}",
                    "path": str(media.path),
                    "name": media.path.name,
                    "category": media.category,
                    "status": "done",
                    "progress": 100.0,
                }
            )

    return rows


class PipelineRunner:
    """Background runner for the pipeline, intended for the Web UI API."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._process_handle = ProcessHandle()
        self._reset_runtime()

    def _reset_runtime(self) -> None:
        self._pipeline_state = "idle"
        self._phase: Optional[str] = None
        self._files: List[Dict[str, Any]] = []
        self._results: List[Tuple[MediaFile, ConversionResult]] = []
        self._convert_queue: List[MediaFile] = []
        self._selection: Dict[str, Dict[str, bool]] = get_pipeline_selection()
        self._current_file = ""
        self._current_progress = 0.0
        self._current_eta = ""
        self._last_error = ""
        self._last_report: Optional[Dict[str, Any]] = None
        self._qbittorrent_actions: List[Dict[str, Any]] = []
        self._started_at: Optional[float] = None
        self._finished_at: Optional[float] = None
        self._stop_requested = False
        self._paused = False

    def scan(self) -> List[Dict[str, Any]]:
        rows = scan_pipeline_files()
        with self._lock:
            if self._pipeline_state not in {"running", "paused", "stopping"}:
                self._files = [dict(row) for row in rows]
        return rows

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "pipeline": self._pipeline_state,
                "phase": self._phase,
                "files": [dict(row) for row in self._files],
                "files_count": len(self._files),
                "current_file": self._current_file,
                "current_progress": self._current_progress,
                "current_eta": self._current_eta,
                "last_error": self._last_error,
                "started_at": self._started_at,
                "finished_at": self._finished_at,
                "selection": self._selection,
                "last_report": self._last_report,
                "qbittorrent": {
                    "enabled": Config.QBITTORRENT_ENABLED and Config.MODIFY_TORRENT_CATEGORY,
                    "actions": list(self._qbittorrent_actions),
                },
                "results": {
                    "ok": sum(1 for _, res in self._results if res.success),
                    "fail": sum(1 for _, res in self._results if not res.success),
                },
            }

    def start(self, selection: Optional[Dict[str, Dict[str, bool]]] = None) -> bool:
        with self._lock:
            if self._pipeline_state in {"running", "paused", "stopping"}:
                return False
            self._reset_runtime()
            self._selection = selection or get_pipeline_selection()
            self._files = scan_pipeline_files()
            self._pipeline_state = "running"
            self._started_at = time.time()
            self._thread = threading.Thread(
                target=self._run_pipeline,
                args=(self._selection,),
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if self._pipeline_state not in {"running", "paused"}:
                return False
            self._stop_requested = True
            self._pipeline_state = "stopping"
            was_paused = self._paused
        if was_paused:
            self.resume()
        self._process_handle.kill()
        return True

    def pause(self) -> bool:
        with self._lock:
            if self._pipeline_state != "running" or self._paused:
                return False
            self._paused = True
            self._pipeline_state = "paused"
        self._process_handle.pause()
        return True

    def resume(self) -> bool:
        with self._lock:
            if self._pipeline_state != "paused" or not self._paused:
                return False
            self._paused = False
            self._pipeline_state = "running"
        self._process_handle.resume()
        return True

    def _set_phase(self, phase: Optional[str]) -> None:
        with self._lock:
            self._phase = phase

    def _set_files(self, rows: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._files = [dict(row) for row in rows]

    def _update_row(self, category: str, filename: str, progress: float, status: Optional[str] = None) -> None:
        basename = Path(filename).name
        with self._lock:
            self._current_file = basename
            self._current_progress = progress
            for row in self._files:
                if row.get("category") == category and row.get("name") == basename:
                    row["progress"] = progress
                    if status:
                        row["status"] = status
                    break

    def _row_id_for_media(self, media: MediaFile) -> str:
        return f"{media.category}:{media.path}"

    def _transform_row_for_media(self, media: MediaFile) -> Dict[str, Any]:
        return {
            "id": self._row_id_for_media(media),
            "path": str(media.path),
            "name": media.path.name,
            "category": media.category,
            "status": "pending",
            "progress": 0.0,
        }

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message

    def _complete(self, state: str) -> None:
        with self._lock:
            self._pipeline_state = state
            self._phase = None
            self._finished_at = time.time()
            self._current_eta = ""

    def _reports_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "reports"

    def _cleanup_converted_source(self, media: MediaFile) -> None:
        """Delete the converted source file from TMP and prune empty folders."""
        try:
            media.path.unlink()
        except FileNotFoundError:
            return
        except Exception as exc:
            self._set_error(f"Warning: failed to delete TMP source {media.path.name}: {exc}")
            return

        root = Config.get_tmp_path(media.category)
        parent = media.path.parent
        while parent != root and root in parent.parents:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def _persist_report(self, state: str) -> None:
        if not self._results and state == "stopped":
            return
        data = ReportData(results=self._results, qbittorrent_actions=self._qbittorrent_actions)
        runtime = {
            "pipeline_state": state,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "selection": self._selection,
        }
        reports_dir = self._reports_dir()
        md_path = save_report(data, directory=reports_dir)
        json_path = save_report_json(data, directory=reports_dir, extra=runtime)
        with self._lock:
            self._last_report = {
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "timestamp": data.timestamp.isoformat(),
            }

    def _apply_qbittorrent_updates(self) -> None:
        """Move successfully processed torrents to the configured processed category."""
        if not (Config.QBITTORRENT_ENABLED and Config.MODIFY_TORRENT_CATEGORY):
            self._qbittorrent_actions = []
            return

        successful_media = [media for media, result in self._results if result.success]
        if not successful_media:
            self._qbittorrent_actions = []
            return

        client = QBittorrentClient()
        if not client.connect():
            self._qbittorrent_actions = [
                {
                    "success": False,
                    "media_name": media.path.name,
                    "source_category": Config.TORRENT_CATEGORIES.get(media.category, media.category),
                    "target_category": Config.PROCESSED_CATEGORY,
                    "error": "Failed to connect to qBittorrent",
                }
                for media in successful_media
            ]
            return

        actions: List[Dict[str, Any]] = []
        seen_batches: set[tuple[str, str]] = set()
        for media in successful_media:
            batch_key = self._qbittorrent_batch_key(media)
            if batch_key in seen_batches:
                continue
            seen_batches.add(batch_key)
            actions.append(
                client.mark_processed_media(
                    media_name=media.path.name,
                    category=media.category,
                    target_category=Config.PROCESSED_CATEGORY,
                )
            )
        self._qbittorrent_actions = actions

    def _qbittorrent_batch_key(self, media: MediaFile) -> tuple[str, str]:
        """Group files that likely belong to the same torrent into one qB action."""
        try:
            relative = media.path.relative_to(Config.get_tmp_path(media.category))
            anchor = relative.parts[0] if relative.parts else media.path.name
            return (media.category, anchor)
        except ValueError:
            return (media.category, media.path.parent.name or media.path.name)

    def latest_report_payload(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            ref = dict(self._last_report) if self._last_report else None
        if not ref:
            history = self.report_history(limit=1)
            if not history:
                return None
            return self.report_payload(history[0]["id"])
        return self.report_payload(Path(ref["json_path"]).stem)

    def report_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return compact metadata for persisted reports."""
        return list_reports(directory=self._reports_dir(), limit=limit)

    def report_payload(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Return full payload for a persisted report by id."""
        json_path = self._reports_dir() / f"{report_id}.json"
        if not json_path.exists():
            return None
        return load_report_json(json_path)

    def reorder_transform_queue(self, ordered_ids: Sequence[str]) -> Dict[str, Any]:
        """Reorder pending transform items to match the requested visible order."""
        with self._lock:
            if self._phase != "transform":
                return self.snapshot()

            desired = [str(item) for item in ordered_ids]
            queue_by_id = {self._row_id_for_media(media): media for media in self._convert_queue}
            reordered = [queue_by_id[item_id] for item_id in desired if item_id in queue_by_id]
            leftovers = [media for media in self._convert_queue if self._row_id_for_media(media) not in desired]
            self._convert_queue = reordered + leftovers

            pending_rows_by_id = {
                row["id"]: dict(row)
                for row in self._files
                if row.get("status") == "pending" and row.get("id") in queue_by_id
            }
            ordered_pending_rows = [
                pending_rows_by_id[item_id]
                for item_id in desired
                if item_id in pending_rows_by_id
            ]
            ordered_pending_ids = {row["id"] for row in ordered_pending_rows}
            ordered_pending_rows.extend(
                row for row in pending_rows_by_id.values() if row["id"] not in ordered_pending_ids
            )

            static_rows = [dict(row) for row in self._files if row.get("status") != "pending"]
            self._files = static_rows + ordered_pending_rows

            return {
                "pipeline": self._pipeline_state,
                "phase": self._phase,
                "files": [dict(row) for row in self._files],
                "files_count": len(self._files),
                "current_file": self._current_file,
                "current_progress": self._current_progress,
                "current_eta": self._current_eta,
                "last_error": self._last_error,
                "started_at": self._started_at,
                "finished_at": self._finished_at,
                "selection": self._selection,
                "last_report": self._last_report,
                "qbittorrent": {
                    "enabled": Config.QBITTORRENT_ENABLED and Config.MODIFY_TORRENT_CATEGORY,
                    "actions": list(self._qbittorrent_actions),
                },
                "results": {
                    "ok": sum(1 for _, res in self._results if res.success),
                    "fail": sum(1 for _, res in self._results if not res.success),
                },
            }

    def _should_stop(self) -> bool:
        with self._lock:
            return self._stop_requested

    def _extract_rows(self, categories: Sequence[str]) -> List[Dict[str, Any]]:
        rows = scan_pipeline_files()
        if categories:
            return [row for row in rows if row["category"] in categories]
        return rows

    def _run_pipeline(self, selection: Dict[str, Dict[str, bool]]) -> None:
        try:
            cats_import = [cat for cat in selection if selection.get(cat, {}).get("importar", True)]
            cats_convert = [cat for cat in selection if selection.get(cat, {}).get("convertir", True)]
            cats_send = [cat for cat in selection if selection.get(cat, {}).get("enviar", True)]

            extract_rows = self._extract_rows(cats_import)
            pending_extract = [
                row for row in extract_rows
                if row.get("status") == "pending" and row.get("category") in cats_import
            ]
            self._set_files(extract_rows)

            if cats_import and pending_extract and Config.TORRENT_BASE.exists():
                self._set_phase("extract")

                def ext_cb(category: str, filename: str, pct: float) -> None:
                    status = "done" if pct >= 100.0 else "active"
                    self._update_row(category, filename, pct, status=status)

                result = ExtractPhase.extract_all(
                    progress_callback=ext_cb,
                    process_handle=self._process_handle,
                    categories=cats_import,
                )
                if not result.success and result.error:
                    self._set_error(result.error)
                    self._complete("error")
                    self._persist_report("error")
                    return

            if self._should_stop():
                self._complete("stopped")
                self._persist_report("stopped")
                return

            media_files: List[MediaFile] = []
            for files in FileDetector.scan_all_categories().values():
                media_files.extend(files)

            files_to_convert = [media for media in media_files if media.category in cats_convert]
            files_to_convert.sort(key=lambda media: (media.category, str(media.path)))
            with self._lock:
                self._convert_queue = list(files_to_convert)
            self._set_phase("transform")
            self._set_files([self._transform_row_for_media(media) for media in files_to_convert])

            while True:
                with self._lock:
                    if not self._convert_queue:
                        break
                    media = self._convert_queue.pop(0)

                if self._should_stop():
                    self._complete("stopped")
                    self._persist_report("stopped")
                    return

                self._update_row(media.category, media.path.name, 0.0, status="active")

                def pcb(pct: float, eta: str, _category=media.category, _name=media.path.name) -> None:
                    with self._lock:
                        self._current_eta = eta
                    status = "done" if pct >= 100.0 else "active"
                    self._update_row(_category, _name, pct, status=status)

                result = MediaConverter.convert(
                    media,
                    progress_callback=pcb,
                    process_handle=self._process_handle,
                )
                self._results.append((media, result))
                if result.success:
                    self._cleanup_converted_source(media)
                    self._update_row(media.category, media.path.name, 100.0, status="done")
                else:
                    self._update_row(media.category, media.path.name, 0.0, status="error")

            if self._should_stop():
                self._complete("stopped")
                self._persist_report("stopped")
                return

            load_rows = [
                {"name": media.path.name, "category": media.category, "status": "pending", "progress": 0.0}
                for media, result in self._results
                if result.success and media.category in cats_send
            ]
            self._set_phase("load")
            self._set_files(load_rows)

            if load_rows and Config.PLEX_DESTINATION.exists():
                def load_cb(category: str, filename: str, pct: float) -> None:
                    status = "done" if pct >= 100.0 else "active"
                    self._update_row(category, filename, pct, status=status)

                result = LoadPhase.load_all(
                    progress_callback=load_cb,
                    process_handle=self._process_handle,
                    categories=cats_send,
                )
                if not result.success and result.error:
                    self._set_error(result.error)
                    self._complete("error")
                    self._persist_report("error")
                    return

            if self._should_stop():
                self._complete("stopped")
                self._persist_report("stopped")
                return

            self._apply_qbittorrent_updates()
            self._complete("completed")
            self._persist_report("completed")
        except Exception as exc:
            self._set_error(str(exc))
            self._complete("error")
            self._persist_report("error")
