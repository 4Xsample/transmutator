"""
Pipeline phases: Extract (Torrent → TMP) and Load (Processed → Plex).

Progress callback signature for transfer phases::

    callback(category: str, filename: str, percent: float)
"""

import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, List, Sequence, Tuple
import logging

from .config import Config

logger = logging.getLogger(__name__)

# Type alias for transfer progress callbacks
TransferCB = Callable[[str, str, float], None]   # (category, filename, percent)

_PCT_RE = re.compile(r"(\d+)%")


# ── Helpers ──────────────────────────────────────────────────────────


class PipelinePhase:
    """Result of a pipeline phase (Extract or Load)."""

    def __init__(self, success: bool, files_transferred: int = 0, error: str = ""):
        self.success = success
        self.files_transferred = files_transferred
        self.error = error


def check_disk_space(path: Path) -> Tuple[bool, int]:
    """Return ``(has_at_least_1GB, available_bytes)``."""
    try:
        target = path if path.exists() else path.parent
        stat = shutil.disk_usage(target)
        return (stat.free >= 1024 ** 3, stat.free)
    except OSError:
        return (False, 0)


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _drain_pipe(pipe, sink: Optional[List[str]] = None) -> None:
    try:
        for line in pipe:
            if sink is not None:
                sink.append(line)
    except Exception:
        pass


_SKIP = ("sending", "sent", "total", "created", "building")


# ── Extract Phase ────────────────────────────────────────────────────


class ExtractPhase:

    @staticmethod
    def _rsync_ok() -> bool:
        return shutil.which("rsync") is not None

    @classmethod
    def extract_category(
        cls,
        category: str,
        progress_callback: Optional[TransferCB] = None,
        process_handle=None,
    ) -> PipelinePhase:
        src = Config.get_torrent_path(category)
        dst = Config.get_tmp_path(category)
        if not src.exists():
            return PipelinePhase(success=True)
        dst.mkdir(parents=True, exist_ok=True)
        if cls._rsync_ok():
            return cls._rsync(src, dst, category, progress_callback, process_handle)
        return cls._shutil(src, dst, category, progress_callback)

    @classmethod
    def _rsync(cls, src, dst, category, cb, handle) -> PipelinePhase:
        cmd = ["rsync", "-avh", "--progress", str(src) + "/", str(dst) + "/"]
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, bufsize=1, start_new_session=True,
            )
            if handle is not None:
                handle.process = proc

            stderr_lines: List[str] = []
            threading.Thread(target=_drain_pipe, args=(proc.stderr, stderr_lines), daemon=True).start()

            files_count = 0
            cur_file: Optional[str] = None

            for raw in proc.stdout:
                stripped = raw.strip()
                if not stripped:
                    continue
                is_indent = raw != raw.lstrip()

                if is_indent and "%" in stripped:
                    m = _PCT_RE.search(stripped)
                    if m and cur_file and cb:
                        cb(category, cur_file, float(m.group(1)))
                elif not stripped.startswith(_SKIP):
                    if not stripped.endswith("/"):
                        cur_file = stripped
                        files_count += 1
                        if cb:
                            cb(category, cur_file, 0.0)

            proc.wait()
            if proc.returncode == 0:
                return PipelinePhase(success=True, files_transferred=files_count)
            tail = "".join(stderr_lines[-5:]).strip()
            return PipelinePhase(success=False, error=f"rsync rc={proc.returncode}: {tail[:300]}")
        except Exception as e:
            return PipelinePhase(success=False, error=str(e))

    @classmethod
    def _shutil(cls, src, dst, category, cb) -> PipelinePhase:
        count = 0
        try:
            for item in src.rglob("*"):
                if not item.is_file():
                    continue
                rel = item.relative_to(src)
                dest = dst / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists() or item.stat().st_mtime > dest.stat().st_mtime:
                    if cb:
                        cb(category, str(rel), 0.0)
                    shutil.copy2(item, dest)
                    count += 1
                    if cb:
                        cb(category, str(rel), 100.0)
            return PipelinePhase(success=True, files_transferred=count)
        except Exception as e:
            return PipelinePhase(success=False, files_transferred=count, error=str(e))

    @classmethod
    def extract_all(
        cls,
        progress_callback: Optional[TransferCB] = None,
        process_handle=None,
        categories: Optional[Sequence[str]] = None,
    ) -> PipelinePhase:
        cats = categories if categories is not None else list(Config.TORRENT_CATEGORIES.values())
        total, errors = 0, []
        for cat in cats:
            r = cls.extract_category(cat, progress_callback, process_handle)
            total += r.files_transferred
            if not r.success and r.error:
                errors.append(r.error)
        if errors:
            return PipelinePhase(success=False, files_transferred=total, error="; ".join(errors))
        return PipelinePhase(success=True, files_transferred=total)


# ── Load Phase ───────────────────────────────────────────────────────


class LoadPhase:

    @staticmethod
    def _rsync_ok() -> bool:
        return shutil.which("rsync") is not None

    @classmethod
    def load_category(
        cls,
        category: str,
        progress_callback: Optional[TransferCB] = None,
        process_handle=None,
    ) -> PipelinePhase:
        src = Config.get_output_path(category)
        dst = Config.get_plex_path(category)
        if not src.exists():
            return PipelinePhase(success=True)
        try:
            if not any(src.iterdir()):
                return PipelinePhase(success=True)
        except OSError:
            return PipelinePhase(success=True)
        dst.mkdir(parents=True, exist_ok=True)
        if cls._rsync_ok():
            return cls._rsync(src, dst, category, progress_callback, process_handle)
        return cls._shutil(src, dst, category, progress_callback)

    @classmethod
    def _rsync(cls, src, dst, category, cb, handle) -> PipelinePhase:
        cmd = ["rsync", "-avh", "--progress", "--remove-source-files",
               str(src) + "/", str(dst) + "/"]
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, bufsize=1, start_new_session=True,
            )
            if handle is not None:
                handle.process = proc

            stderr_lines: List[str] = []
            threading.Thread(target=_drain_pipe, args=(proc.stderr, stderr_lines), daemon=True).start()

            count = 0
            cur_file: Optional[str] = None

            for raw in proc.stdout:
                stripped = raw.strip()
                if not stripped:
                    continue
                is_indent = raw != raw.lstrip()

                if is_indent and "%" in stripped:
                    m = _PCT_RE.search(stripped)
                    if m and cur_file and cb:
                        cb(category, cur_file, float(m.group(1)))
                elif not stripped.startswith(_SKIP):
                    if not stripped.endswith("/"):
                        cur_file = stripped
                        count += 1
                        if cb:
                            cb(category, cur_file, 0.0)

            proc.wait()
            if proc.returncode == 0:
                return PipelinePhase(success=True, files_transferred=count)
            tail = "".join(stderr_lines[-5:]).strip()
            return PipelinePhase(success=False, error=f"rsync rc={proc.returncode}: {tail[:300]}")
        except Exception as e:
            return PipelinePhase(success=False, error=str(e))

    @classmethod
    def _shutil(cls, src, dst, category, cb) -> PipelinePhase:
        count = 0
        try:
            for item in src.rglob("*"):
                if not item.is_file():
                    continue
                rel = item.relative_to(src)
                dest = dst / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if cb:
                    cb(category, str(rel), 0.0)
                shutil.move(str(item), str(dest))
                count += 1
                if cb:
                    cb(category, str(rel), 100.0)
            return PipelinePhase(success=True, files_transferred=count)
        except Exception as e:
            return PipelinePhase(success=False, files_transferred=count, error=str(e))

    @classmethod
    def load_all(
        cls,
        progress_callback: Optional[TransferCB] = None,
        process_handle=None,
        categories: Optional[Sequence[str]] = None,
    ) -> PipelinePhase:
        cats = categories if categories is not None else list(Config.TORRENT_CATEGORIES.values())
        total, errors = 0, []
        for cat in cats:
            r = cls.load_category(cat, progress_callback, process_handle)
            total += r.files_transferred
            if not r.success and r.error:
                errors.append(r.error)
        if errors:
            return PipelinePhase(success=False, files_transferred=total, error="; ".join(errors))
        return PipelinePhase(success=True, files_transferred=total)
