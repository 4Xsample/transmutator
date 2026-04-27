"""
Conversion module for video and audio files.

Handles HandBrakeCLI (video) and FFmpeg (audio) conversions.

Debug HandBrake progress: run with TRANSMUTATOR_DEBUG_HANDBRAKE=1 to write
every line from HandBrake stdout/stderr to handbrake_debug.log (current dir).
Use it to see exactly what your HandBrake version outputs for progress.
"""

import json
import os
import queue
import re
import signal
import subprocess
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
import logging

# Pseudo-TTY per forçar line-buffering de HandBrake (només Unix)
try:
    import pty
    _PTY_AVAILABLE = sys.platform != "win32"
except ImportError:
    pty = None  # type: ignore
    _PTY_AVAILABLE = False

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


def _stdout_reader(pipe, out_queue: queue.Queue) -> None:
    """Read stdout line by line and put into queue; put None when done."""
    try:
        for line in pipe:
            out_queue.put(line)
    except Exception:
        pass
    finally:
        out_queue.put(None)


def _collect_multiline_json(lines: List[str]) -> Optional[str]:
    """Given lines like 'Progress: {', '    "State": "WORKING",', ... '}',
    return the complete JSON string (from first { to matching }) or None.
    """
    combined = "\n".join(lines)
    i = combined.find("{")
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(combined)):
        if combined[j] == "{":
            depth += 1
        elif combined[j] == "}":
            depth -= 1
            if depth == 0:
                return combined[i : j + 1]
    return None


def _try_json_progress(
    line: str,
    progress_callback: Callable[[float, str], None],
    format_eta_fn: Callable[[float], str],
) -> bool:
    """Si *line* és JSON amb Progress/ETA, crida progress_callback i retorna True."""
    line = line.strip()
    if not line or not line.startswith("{"):
        return False
    try:
        data = json.loads(line)
        res = _extract_progress_eta(data)
        if res is not None:
            percent, eta_sec = res
            progress_callback(percent, format_eta_fn(eta_sec))
            return True
        state = (data.get("State") or data.get("state") or "").strip()
        if state == "WORKING":
            working = data.get("Working") or data.get("working") or {}
            if isinstance(working, dict):
                prog = working.get("Progress", working.get("progress", 0.0))
                if isinstance(prog, (int, float)):
                    pct = float(prog) * 100.0 if prog <= 1.0 else float(prog)
                else:
                    return False
                eta_sec = working.get("ETASeconds", working.get("etaSeconds", 0)) or 0
                progress_callback(pct, format_eta_fn(float(eta_sec)))
                return True
        elif state == "SCANNING":
            scanning = data.get("Scanning") or data.get("scanning") or {}
            if isinstance(scanning, dict):
                sp = scanning.get("Progress", scanning.get("progress", 0.0)) or 0.0
                scan_pct = float(sp) * 5.0 if float(sp) <= 1.0 else min(5.0, float(sp))
                progress_callback(scan_pct, "Escanejant…")
                return True
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        pass
    return False


def _stderr_progress_reader(
    pipe,
    sink: List[str],
    progress_callback: Optional[Callable[[float, str], None]],
    text_parser: Callable[[str, Callable[[float, str], None]], None],
    format_eta_fn: Optional[Callable[[float], str]] = None,
    debug_file: Optional[Any] = None,
) -> None:
    """Llegeix stderr: desa línies, intenta JSON progress, i si no text progress (%)."""
    format_eta_fn = format_eta_fn or _format_eta
    try:
        for line in pipe:
            sink.append(line)
            if debug_file:
                try:
                    debug_file.write(f"[stderr] {line}")
                    debug_file.flush()
                except Exception:
                    pass
            if not progress_callback:
                continue
            if _try_json_progress(line, progress_callback, format_eta_fn):
                continue
            if "%" in line:
                text_parser(line, progress_callback)
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


def _extract_progress_eta(data: Dict[str, Any]) -> Optional[tuple]:
    """Extreu (percent, eta_seconds) d'un dict HandBrake si hi ha Progress/ETASeconds.
    Cerca a primer nivell i dins de Working/working. Retorna None si no hi ha dades.
    """
    percent = None
    eta_sec = None
    for key in ("Working", "working"):
        block = data.get(key)
        if isinstance(block, dict):
            p = block.get("Progress", block.get("progress"))
            e = block.get("ETASeconds", block.get("etaSeconds"))
            if p is not None:
                try:
                    percent = float(p) * 100.0 if float(p) <= 1.0 else float(p)
                except (TypeError, ValueError):
                    pass
            if e is not None:
                try:
                    eta_sec = float(e)
                except (TypeError, ValueError):
                    pass
            if percent is not None:
                break
    if percent is None:
        p = data.get("Progress", data.get("progress"))
        if p is not None:
            try:
                percent = float(p) * 100.0 if float(p) <= 1.0 else float(p)
            except (TypeError, ValueError):
                pass
    if eta_sec is None:
        e = data.get("ETASeconds", data.get("etaSeconds"))
        if e is not None:
            try:
                eta_sec = float(e)
            except (TypeError, ValueError):
                pass
    if percent is not None:
        return (percent, eta_sec or 0)
    return None


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

        # Build HandBrakeCLI command — --json envia progress en JSON (stdout o stderr segons versió)
        cmd = [
            Config.HANDBRAKE_CLI,
            "--preset-import-file", str(Config.HANDBRAKE_PRESETS_PATH),
            "--input", str(input_file),
            "--output", str(output_file),
            "--preset", preset,
            "--json",
        ]
        if not _PTY_AVAILABLE:
            stdbuf = shutil.which("stdbuf")
            if stdbuf:
                cmd = [stdbuf, "-oL", "-e0"] + cmd

        debug_file = None
        if os.environ.get("TRANSMUTATOR_DEBUG_HANDBRAKE"):
            try:
                debug_file = open("handbrake_debug.log", "a", encoding="utf-8")
                debug_file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} {input_file.name} ---\n")
                debug_file.flush()
            except Exception:
                debug_file = None

        try:
            start_time = time.time()
            stdout_queue: queue.Queue = queue.Queue()
            stdout_stream = None
            slave_fd = None

            if _PTY_AVAILABLE and pty is not None:
                master_fd, slave_fd = pty.openpty()
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=slave_fd,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        bufsize=1,
                        start_new_session=True,
                    )
                    os.close(slave_fd)
                    slave_fd = None
                    stdout_stream = os.fdopen(master_fd, "r", encoding="utf-8", errors="replace")
                except Exception:
                    if slave_fd is not None:
                        try:
                            os.close(slave_fd)
                        except OSError:
                            pass
                    try:
                        os.close(master_fd)
                    except OSError:
                        pass
                    raise
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1,
                    start_new_session=True,
                )
                stdout_stream = process.stdout

            if process_handle is not None:
                process_handle.process = process

            stdout_thread = threading.Thread(
                target=_stdout_reader, args=(stdout_stream, stdout_queue), daemon=True
            )
            stdout_thread.start()

            # Stderr: errors + parsejar JSON o text progress (segons on escrigui HandBrake)
            # HandBrake often writes progress to stderr; parsing it gives us % and ETA.
            stderr_lines: List[str] = []
            stderr_thread = threading.Thread(
                target=_stderr_progress_reader,
                args=(
                    process.stderr,
                    stderr_lines,
                    progress_callback,
                    cls._parse_text_progress,
                    _format_eta,
                    debug_file,
                ),
                daemon=True,
            )
            stderr_thread.start()

            # --- Process stdout (JSON progress) from queue ---
            # HandBrake 1.10+ envia JSON multilínia ("Progress: { ... }"); cal acumular línies
            json_buffer: List[str] = []
            while True:
                line = stdout_queue.get()
                if line is None:
                    break
                if debug_file:
                    try:
                        debug_file.write(f"[stdout] {line}")
                        debug_file.flush()
                    except Exception:
                        pass
                raw = line
                line = line.strip()
                if not line:
                    continue

                if line.startswith("Progress:") or line.startswith("Version:"):
                    json_buffer = [raw.strip()]
                    continue
                if json_buffer:
                    json_buffer.append(raw.strip())
                    json_str = _collect_multiline_json(json_buffer)
                    if json_str is not None:
                        json_buffer = []
                        if progress_callback:
                            try:
                                data = json.loads(json_str)
                                state = (data.get("State") or data.get("state") or "").strip()
                                if state == "WORKING":
                                    working = data.get("Working") or data.get("working") or {}
                                    if isinstance(working, dict):
                                        prog = working.get("Progress", working.get("progress", 0.0))
                                        if isinstance(prog, (int, float)):
                                            percent = float(prog) * 100.0 if prog <= 1.0 else float(prog)
                                        else:
                                            percent = 0.0
                                        eta_sec = working.get("ETASeconds", working.get("etaSeconds", 0)) or 0
                                        eta = _format_eta(float(eta_sec))
                                        progress_callback(percent, eta)
                                elif state == "SCANNING":
                                    scanning = data.get("Scanning") or data.get("scanning") or {}
                                    if isinstance(scanning, dict):
                                        scan_prog = scanning.get("Progress", scanning.get("progress", 0.0)) or 0.0
                                        scan_pct = float(scan_prog) * 5.0 if scan_prog <= 1.0 else min(5.0, float(scan_prog))
                                        progress_callback(scan_pct, "Escanejant…")
                                else:
                                    res = _extract_progress_eta(data)
                                    if res is not None:
                                        percent, eta_sec = res
                                        progress_callback(percent, _format_eta(eta_sec))
                            except (json.JSONDecodeError, TypeError, ValueError):
                                pass
                    continue

                # JSON d'una sola línia (versions antigues)
                if progress_callback:
                    try:
                        data = json.loads(line)
                        state = (data.get("State") or data.get("state") or "").strip()
                        if state == "WORKING":
                            working = data.get("Working") or data.get("working") or {}
                            if isinstance(working, dict):
                                prog = working.get("Progress", working.get("progress", 0.0))
                                if isinstance(prog, (int, float)):
                                    percent = float(prog) * 100.0 if prog <= 1.0 else float(prog)
                                else:
                                    percent = 0.0
                                eta_sec = working.get("ETASeconds", working.get("etaSeconds", 0)) or 0
                                eta = _format_eta(float(eta_sec))
                                progress_callback(percent, eta)
                        elif state == "SCANNING":
                            scanning = data.get("Scanning") or data.get("scanning") or {}
                            if isinstance(scanning, dict):
                                scan_prog = scanning.get("Progress", scanning.get("progress", 0.0)) or 0.0
                                scan_pct = float(scan_prog) * 5.0 if scan_prog <= 1.0 else min(5.0, float(scan_prog))
                                progress_callback(scan_pct, "Escanejant…")
                        else:
                            res = _extract_progress_eta(data)
                            if res is not None:
                                percent, eta_sec = res
                                progress_callback(percent, _format_eta(eta_sec))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        cls._parse_text_progress(line, progress_callback)

            process.wait()
            stdout_thread.join(timeout=5)
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
        finally:
            if debug_file is not None:
                try:
                    debug_file.close()
                except Exception:
                    pass

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _parse_text_progress(
        line: str, callback: Callable[[float, str], None]
    ) -> None:
        """Parser per qualsevol línia que sembli progrés (percentatge i opcionalment ETA).

        Accepta HandBrake stderr, stdout no-JSON, o qualsevol text amb XX.X% i ETA.
        Exemples::
            Encoding: task 1 of 1, 45.23 % (120 fps, ETA 00h12m34s)
            45.23 % ETA 00:12:34
            [progress] 45.2%
        """
        if "%" not in line:
            return
        try:
            # Cerca el primer percentatge (nombre amb decimals + %)
            match = re.search(r"(\d+\.?\d*)\s*%", line)
            if not match:
                return
            percent = float(match.group(1))
            if percent < 0 or percent > 100:
                return
            # ETA: diverses formes (ETA 00h12m34s, ETA 00:12:34, eta 00:12:34)
            eta = ""
            eta_match = re.search(r"ETA\s*[:\s]+([\d:hmss]+)", line, re.IGNORECASE)
            if eta_match:
                eta = eta_match.group(1).strip()
                if ":" in eta and "h" not in eta.lower():
                    parts = eta.split(":")
                    if len(parts) >= 3:
                        try:
                            eta = f"{int(parts[0]):02d}h{int(parts[1]):02d}m{int(parts[2]):02d}s"
                        except (ValueError, IndexError):
                            pass
            callback(percent, eta)
        except (ValueError, IndexError, TypeError):
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

    @staticmethod
    def _default_output_path(media_file: MediaFile) -> Path:
        """Build the default output path, preserving relative folder structure."""
        output_dir = Config.get_output_path(media_file.category)
        target_name = media_file.path.name
        if (
            media_file.media_type == MediaType.AUDIO
            and media_file.path.suffix.lower() in Config.AUDIO_LOSSLESS_EXTENSIONS
        ):
            target_name = f"{media_file.path.stem}.{Config.AUDIO_TARGET_FORMAT}"

        try:
            relative = media_file.path.relative_to(Config.get_tmp_path(media_file.category))
            parent = relative.parent
        except ValueError:
            parent = Path()

        return output_dir / parent / target_name

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
            output_path = cls._default_output_path(media_file)

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
