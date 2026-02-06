"""
Conversion module for video and audio files.

Handles HandBrakeCLI (video) and FFmpeg (audio) conversions.
"""

import json
import os
import re
import signal
import subprocess
import shutil
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
import logging

from .config import Config
from .file_detector import MediaFile, MediaType

logger = logging.getLogger(__name__)


def _drain_pipe(pipe, sink: Optional[List[str]] = None) -> None:
    """Read all output from a pipe in background to prevent deadlocks.

    If *sink* is provided, lines are appended there for later inspection
    (e.g. error reporting).
    """
    try:
        for line in pipe:
            if sink is not None:
                sink.append(line)
    except Exception:
        pass


def _format_eta(seconds: float) -> str:
    """Convert seconds into a human-readable ETA string (e.g. '01h23m45s')."""
    if seconds <= 0:
        return ""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h{m:02d}m{s:02d}s"


class ProcessHandle:
    """Mutable handle to control a running subprocess (pause/stop).

    Pass an instance to the converter so it can register the subprocess.
    The TUI can then call :meth:`kill`, :meth:`pause` or :meth:`resume`
    from the main thread while the conversion runs in a worker thread.
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self._paused = False

    def kill(self) -> None:
        """Kill the subprocess and all its children immediately."""
        if self.process is None or self.process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                self.process.kill()
            except (ProcessLookupError, OSError):
                pass
        self._paused = False

    def pause(self) -> None:
        """Pause the subprocess (SIGSTOP)."""
        if self.process is None or self.process.poll() is not None or self._paused:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGSTOP)
            self._paused = True
        except (ProcessLookupError, OSError):
            pass

    def resume(self) -> None:
        """Resume the subprocess (SIGCONT)."""
        if self.process is None or self.process.poll() is not None or not self._paused:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGCONT)
            self._paused = False
        except (ProcessLookupError, OSError):
            pass

    @property
    def is_paused(self) -> bool:
        return self._paused


class ConversionResult:
    """Result of a conversion operation."""

    def __init__(
        self,
        success: bool,
        output_path: Optional[Path] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        original_size: Optional[int] = None,
        output_size: Optional[int] = None
    ):
        self.success = success
        self.output_path = output_path
        self.error = error
        self.duration_seconds = duration_seconds
        self.original_size = original_size
        self.output_size = output_size or (output_path.stat().st_size if output_path and output_path.exists() else None)


class VideoConverter:
    """Handles video conversion using HandBrakeCLI."""

    @staticmethod
    def is_handbrake_available() -> bool:
        """Check if HandBrakeCLI is available."""
        return shutil.which(Config.HANDBRAKE_CLI) is not None

    @staticmethod
    def get_preset_for_category(category: str) -> str:
        """Get the HandBrake preset name for a category."""
        if category == "radarr":
            return Config.VIDEO_PRESET_MOVIES
        elif category == "tv-sonarr":
            return Config.VIDEO_PRESET_SERIES
        else:
            return Config.VIDEO_PRESET_MOVIES  # Default

    @classmethod
    def convert(
        cls,
        input_file: Path,
        output_file: Path,
        category: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        process_handle: Optional[ProcessHandle] = None,
    ) -> ConversionResult:
        """
        Convert a video file using HandBrakeCLI.

        Uses ``--json`` so that stdout emits one JSON object per state
        change.  The actual format is::

            {"State":"WORKING","Working":{"Progress":0.45,"ETASeconds":754,...}}

        Args:
            input_file: Input video file path
            output_file: Output video file path
            category: Category (radarr/tv-sonarr) to determine preset
            progress_callback: Optional callback for progress updates (percent, eta)
            process_handle: Optional ProcessHandle for pause/stop control

        Returns:
            ConversionResult object
        """
        if not cls.is_handbrake_available():
            return ConversionResult(
                success=False,
                error=f"HandBrakeCLI not found. Is '{Config.HANDBRAKE_CLI}' installed?"
            )

        if not input_file.exists():
            return ConversionResult(
                success=False,
                error=f"Input file does not exist: {input_file}"
            )

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        preset = cls.get_preset_for_category(category)
        original_size = input_file.stat().st_size

        # Build HandBrakeCLI command — --json gives structured progress on stdout
        cmd = [
            Config.HANDBRAKE_CLI,
            "--input", str(input_file),
            "--output", str(output_file),
            "--preset", preset,
            "--json",
        ]

        try:
            start_time = time.time()

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

            # Drain stderr in a background thread to prevent pipe deadlock.
            # We keep the lines for error reporting if the process fails.
            stderr_lines: List[str] = []
            stderr_thread = threading.Thread(
                target=_drain_pipe, args=(process.stderr, stderr_lines), daemon=True
            )
            stderr_thread.start()

            # --- Parse stdout (JSON progress) ---
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                if progress_callback:
                    try:
                        data = json.loads(line)
                        state = data.get("State", "")

                        if state == "WORKING":
                            working = data.get("Working", {})
                            # Progress is 0.0 – 1.0
                            percent = working.get("Progress", 0.0) * 100.0
                            eta = _format_eta(working.get("ETASeconds", 0))
                            progress_callback(percent, eta)

                        elif state == "SCANNING":
                            scanning = data.get("Scanning", {})
                            # Show scanning as 0-5 % so the bar gives feedback
                            scan_pct = scanning.get("Progress", 0.0) * 5.0
                            progress_callback(scan_pct, "Escanejant…")

                    except json.JSONDecodeError:
                        # Fallback: plain-text progress (some HB versions)
                        cls._parse_text_progress(line, progress_callback)

            process.wait()
            stderr_thread.join(timeout=5)
            duration = time.time() - start_time

            if process.returncode == 0 and output_file.exists():
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size,
                )
            else:
                tail = "".join(stderr_lines[-10:]).strip()
                error_msg = tail[:500] if tail else f"Exit code {process.returncode}"
                return ConversionResult(
                    success=False,
                    error=f"HandBrakeCLI: {error_msg}",
                    duration_seconds=duration,
                    original_size=original_size,
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                error=f"Conversion failed: {str(e)}",
                original_size=original_size,
            )

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _parse_text_progress(
        line: str, callback: Callable[[float, str], None]
    ) -> None:
        """Fallback parser for non-JSON HandBrake output.

        Matches lines like::

            Encoding: task 1 of 1, 45.23 % (120 fps, avg 115 fps, ETA 00h12m34s)
        """
        if "Encoding:" not in line or "%" not in line:
            return
        try:
            match = re.search(r"([\d.]+)\s*%", line)
            if match:
                percent = float(match.group(1))
                eta_match = re.search(r"ETA\s+([\dhms]+)", line)
                eta = eta_match.group(1) if eta_match else ""
                callback(percent, eta)
        except (ValueError, IndexError):
            pass


class AudioConverter:
    """Handles audio conversion using FFmpeg."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Check if FFmpeg is available."""
        return shutil.which(Config.FFMPEG_BIN) is not None

    @staticmethod
    def is_lossy_format(file_path: Path) -> bool:
        """Check if audio file is in a lossy format."""
        return file_path.suffix.lower() in Config.AUDIO_LOSSY_EXTENSIONS

    @staticmethod
    def is_lossless_format(file_path: Path) -> bool:
        """Check if audio file is in a lossless format."""
        return file_path.suffix.lower() in Config.AUDIO_LOSSLESS_EXTENSIONS

    @classmethod
    def _probe_duration(cls, input_file: Path) -> Optional[float]:
        """Get audio duration in seconds via ffprobe (shipped with FFmpeg)."""
        ffprobe = Config.FFMPEG_BIN.replace("ffmpeg", "ffprobe")
        if shutil.which(ffprobe) is None:
            return None
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(input_file),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return None

    @classmethod
    def convert(
        cls,
        input_file: Path,
        output_file: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        process_handle: Optional[ProcessHandle] = None,
    ) -> ConversionResult:
        """
        Convert an audio file using FFmpeg.

        For lossy formats (MP3, AAC, etc.), just copies the file.
        For lossless formats (FLAC, WAV, etc.), converts to MP3 320kbps.

        Args:
            input_file: Input audio file path
            output_file: Output audio file path
            progress_callback: Optional callback for progress updates
            process_handle: Optional ProcessHandle for pause/stop control

        Returns:
            ConversionResult object
        """
        if not cls.is_ffmpeg_available():
            return ConversionResult(
                success=False,
                error=f"FFmpeg not found. Is '{Config.FFMPEG_BIN}' installed?",
            )

        if not input_file.exists():
            return ConversionResult(
                success=False,
                error=f"Input file does not exist: {input_file}",
            )

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        original_size = input_file.stat().st_size

        # If lossy format, just copy (no re-encoding)
        if cls.is_lossy_format(input_file):
            try:
                start_time = time.time()
                shutil.copy2(input_file, output_file)
                duration = time.time() - start_time
                if progress_callback:
                    progress_callback(100.0, "")
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size,
                )
            except Exception as e:
                return ConversionResult(
                    success=False,
                    error=f"Copy failed: {str(e)}",
                    original_size=original_size,
                )

        # Get total duration so we can report percentage
        total_duration = cls._probe_duration(input_file)

        # For lossless formats, convert to MP3 320kbps
        cmd = [
            Config.FFMPEG_BIN,
            "-i", str(input_file),
            "-codec:a", "libmp3lame",
            "-b:a", Config.AUDIO_TARGET_BITRATE,
            "-y",
            str(output_file),
        ]

        try:
            start_time = time.time()

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

            # Drain stdout in background (FFmpeg writes nothing useful there)
            stdout_thread = threading.Thread(
                target=_drain_pipe, args=(process.stdout,), daemon=True
            )
            stdout_thread.start()

            # Parse stderr for progress.
            # FFmpeg emits CR-terminated lines like:
            #   size= 1234kB time=00:01:23.45 bitrate=320.0kbits/s speed=2.3x
            # Python text-mode translates \r to \n, so iteration works.
            stderr_lines: List[str] = []
            _TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

            for line in process.stderr:
                stderr_lines.append(line)
                if progress_callback and "time=" in line:
                    match = _TIME_RE.search(line)
                    if match:
                        h, m, s, cs = (
                            int(match.group(1)),
                            int(match.group(2)),
                            int(match.group(3)),
                            int(match.group(4)),
                        )
                        current = h * 3600 + m * 60 + s + cs / 100.0
                        if total_duration and total_duration > 0:
                            percent = min(99.0, (current / total_duration) * 100.0)
                            remaining = max(0, total_duration - current)
                            progress_callback(percent, _format_eta(remaining))
                        else:
                            # Can't calculate %; just pulse a generic value
                            progress_callback(50.0, "")

            process.wait()
            stdout_thread.join(timeout=5)
            duration = time.time() - start_time

            if process.returncode == 0 and output_file.exists():
                if progress_callback:
                    progress_callback(100.0, "")
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size,
                )
            else:
                tail = "".join(stderr_lines[-5:]).strip()
                return ConversionResult(
                    success=False,
                    error=f"FFmpeg: {tail[:300]}" if tail else "FFmpeg error desconegut",
                    duration_seconds=duration,
                    original_size=original_size,
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                error=f"Conversion failed: {str(e)}",
                original_size=original_size,
            )


class MediaConverter:
    """Main converter class that routes to appropriate converter."""

    @classmethod
    def convert(
        cls,
        media_file: MediaFile,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        process_handle: Optional[ProcessHandle] = None,
    ) -> ConversionResult:
        """
        Convert a media file based on its type.

        Args:
            media_file: MediaFile object to convert
            output_path: Optional output path override
            progress_callback: Optional progress callback
            process_handle: Optional ProcessHandle for pause/stop control

        Returns:
            ConversionResult object
        """
        if output_path is None:
            output_dir = Config.get_output_path(media_file.category)
            if media_file.media_type == MediaType.AUDIO and media_file.path.suffix.lower() in Config.AUDIO_LOSSLESS_EXTENSIONS:
                output_path = output_dir / (media_file.path.stem + "." + Config.AUDIO_TARGET_FORMAT)
            else:
                output_path = output_dir / media_file.path.name

        if media_file.media_type == MediaType.VIDEO:
            return VideoConverter.convert(
                media_file.path,
                output_path,
                media_file.category,
                progress_callback,
                process_handle,
            )
        elif media_file.media_type == MediaType.AUDIO:
            return AudioConverter.convert(
                media_file.path,
                output_path,
                progress_callback,
                process_handle,
            )
        else:
            return ConversionResult(
                success=False,
                error=f"Unknown media type: {media_file.media_type}"
            )
