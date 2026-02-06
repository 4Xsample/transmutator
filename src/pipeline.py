"""
Pipeline phases: Extract (Torrent → TMP) and Load (Processed → Plex).

Includes disk-space utilities.
"""

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, List, Tuple
import logging

from .config import Config

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


class PipelinePhase:
    """Result of a pipeline phase (Extract or Load)."""

    def __init__(
        self,
        success: bool,
        files_transferred: int = 0,
        error: str = "",
    ):
        self.success = success
        self.files_transferred = files_transferred
        self.error = error


def check_disk_space(path: Path) -> Tuple[bool, int]:
    """Check available disk space at *path*.

    Returns:
        ``(has_reasonable_space, available_bytes)``.
        *has_reasonable_space* is ``True`` when at least 1 GB is free.
    """
    try:
        target = path if path.exists() else path.parent
        stat = shutil.disk_usage(target)
        threshold = 1 * 1024 * 1024 * 1024  # 1 GB
        return (stat.free >= threshold, stat.free)
    except OSError:
        return (False, 0)


def format_size(size_bytes: int) -> str:
    """Format *size_bytes* to a human-readable string."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _drain_pipe(pipe, sink: Optional[List[str]] = None) -> None:
    """Read all output from a pipe to prevent deadlocks."""
    try:
        for line in pipe:
            if sink is not None:
                sink.append(line)
    except Exception:
        pass


# ── Extract Phase ────────────────────────────────────────────────────


class ExtractPhase:
    """Extract: copy files from torrent directories to TMP staging."""

    @staticmethod
    def _rsync_available() -> bool:
        return shutil.which("rsync") is not None

    @classmethod
    def extract_category(
        cls,
        category: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        process_handle=None,
    ) -> PipelinePhase:
        """Copy files for *category* from the torrent dir to TMP staging.

        Args:
            category: Category name (tv-sonarr, radarr, lidarr).
            progress_callback: Callback receiving status strings.
            process_handle: Optional :class:`ProcessHandle` for pause/stop.
        """
        src = Config.get_torrent_path(category)
        dst = Config.get_tmp_path(category)

        if not src.exists():
            return PipelinePhase(success=True, files_transferred=0)

        dst.mkdir(parents=True, exist_ok=True)

        if cls._rsync_available():
            return cls._extract_rsync(src, dst, progress_callback, process_handle)
        return cls._extract_shutil(src, dst, progress_callback)

    @classmethod
    def _extract_rsync(
        cls,
        src: Path,
        dst: Path,
        callback: Optional[Callable[[str], None]],
        process_handle,
    ) -> PipelinePhase:
        cmd = [
            "rsync",
            "-avh",
            "--progress",
            str(src) + "/",
            str(dst) + "/",
        ]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True,
            )
            if process_handle is not None:
                process_handle.process = process

            # Drain stderr in background
            stderr_lines: List[str] = []
            stderr_thread = threading.Thread(
                target=_drain_pipe, args=(process.stderr, stderr_lines), daemon=True
            )
            stderr_thread.start()

            files_count = 0
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                # Show file-level status, skip rsync summary lines
                skip_prefixes = ("sending", "sent", "total", "created", "building")
                if callback and not line.startswith(skip_prefixes):
                    callback(f"Copiant: {line}")
                # Count transferred files (skip dirs, progress lines, summaries)
                if (
                    not line.endswith("/")
                    and "%" not in line
                    and "to-chk=" not in line
                    and not line.startswith(skip_prefixes)
                ):
                    files_count += 1

            process.wait()
            stderr_thread.join(timeout=5)

            if process.returncode == 0:
                return PipelinePhase(success=True, files_transferred=files_count)
            else:
                tail = "".join(stderr_lines[-5:]).strip()
                return PipelinePhase(
                    success=False,
                    error=f"rsync error (rc={process.returncode}): {tail[:300]}",
                )
        except Exception as e:
            return PipelinePhase(success=False, error=str(e))

    @classmethod
    def _extract_shutil(
        cls,
        src: Path,
        dst: Path,
        callback: Optional[Callable[[str], None]],
    ) -> PipelinePhase:
        """Fallback: incremental copy with :mod:`shutil`."""
        files_count = 0
        try:
            for item in src.rglob("*"):
                if not item.is_file():
                    continue
                relative = item.relative_to(src)
                dest_file = dst / relative
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                # Only copy if newer or not present
                if (
                    not dest_file.exists()
                    or item.stat().st_mtime > dest_file.stat().st_mtime
                ):
                    shutil.copy2(item, dest_file)
                    files_count += 1
                    if callback:
                        callback(f"Copiant: {relative}")
            return PipelinePhase(success=True, files_transferred=files_count)
        except Exception as e:
            return PipelinePhase(
                success=False,
                files_transferred=files_count,
                error=str(e),
            )

    @classmethod
    def extract_all(
        cls,
        progress_callback: Optional[Callable[[str], None]] = None,
        process_handle=None,
    ) -> PipelinePhase:
        """Extract all categories (continues on per-category errors)."""
        total_files = 0
        errors: List[str] = []
        for category in Config.TORRENT_CATEGORIES.values():
            result = cls.extract_category(
                category, progress_callback, process_handle
            )
            total_files += result.files_transferred
            if not result.success and result.error:
                errors.append(result.error)
        if errors:
            return PipelinePhase(
                success=False,
                files_transferred=total_files,
                error="; ".join(errors),
            )
        return PipelinePhase(success=True, files_transferred=total_files)


# ── Load Phase ───────────────────────────────────────────────────────


class LoadPhase:
    """Load: move processed files to Plex destination."""

    @staticmethod
    def _rsync_available() -> bool:
        return shutil.which("rsync") is not None

    @classmethod
    def load_category(
        cls,
        category: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        process_handle=None,
    ) -> PipelinePhase:
        """Move processed files for *category* to the Plex destination."""
        src = Config.get_output_path(category)
        dst = Config.get_plex_path(category)

        if not src.exists():
            return PipelinePhase(success=True, files_transferred=0)

        # Skip if directory is empty
        try:
            if not any(src.iterdir()):
                return PipelinePhase(success=True, files_transferred=0)
        except (OSError, StopIteration):
            return PipelinePhase(success=True, files_transferred=0)

        dst.mkdir(parents=True, exist_ok=True)

        if cls._rsync_available():
            return cls._load_rsync(src, dst, progress_callback, process_handle)
        return cls._load_shutil(src, dst, progress_callback)

    @classmethod
    def _load_rsync(
        cls,
        src: Path,
        dst: Path,
        callback: Optional[Callable[[str], None]],
        process_handle,
    ) -> PipelinePhase:
        cmd = [
            "rsync",
            "-avh",
            "--progress",
            "--remove-source-files",
            str(src) + "/",
            str(dst) + "/",
        ]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True,
            )
            if process_handle is not None:
                process_handle.process = process

            stderr_lines: List[str] = []
            stderr_thread = threading.Thread(
                target=_drain_pipe, args=(process.stderr, stderr_lines), daemon=True
            )
            stderr_thread.start()

            files_count = 0
            skip_prefixes = ("sending", "sent", "total", "created", "building")
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                if callback and not line.startswith(skip_prefixes):
                    callback(f"Enviant: {line}")
                if (
                    not line.endswith("/")
                    and "%" not in line
                    and "to-chk=" not in line
                    and not line.startswith(skip_prefixes)
                ):
                    files_count += 1

            process.wait()
            stderr_thread.join(timeout=5)

            if process.returncode == 0:
                return PipelinePhase(success=True, files_transferred=files_count)
            else:
                tail = "".join(stderr_lines[-5:]).strip()
                return PipelinePhase(
                    success=False,
                    error=f"rsync error (rc={process.returncode}): {tail[:300]}",
                )
        except Exception as e:
            return PipelinePhase(success=False, error=str(e))

    @classmethod
    def _load_shutil(
        cls,
        src: Path,
        dst: Path,
        callback: Optional[Callable[[str], None]],
    ) -> PipelinePhase:
        """Fallback: move with :func:`shutil.move`."""
        files_count = 0
        try:
            for item in src.rglob("*"):
                if not item.is_file():
                    continue
                relative = item.relative_to(src)
                dest_file = dst / relative
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(item), str(dest_file))
                files_count += 1
                if callback:
                    callback(f"Enviant: {relative}")
            return PipelinePhase(success=True, files_transferred=files_count)
        except Exception as e:
            return PipelinePhase(
                success=False,
                files_transferred=files_count,
                error=str(e),
            )

    @classmethod
    def load_all(
        cls,
        progress_callback: Optional[Callable[[str], None]] = None,
        process_handle=None,
    ) -> PipelinePhase:
        """Move all processed files to Plex (continues on per-category errors)."""
        total_files = 0
        errors: List[str] = []
        for category in Config.TORRENT_CATEGORIES.values():
            result = cls.load_category(
                category, progress_callback, process_handle
            )
            total_files += result.files_transferred
            if not result.success and result.error:
                errors.append(result.error)
        if errors:
            return PipelinePhase(
                success=False,
                files_transferred=total_files,
                error="; ".join(errors),
            )
        return PipelinePhase(success=True, files_transferred=total_files)
