"""
Conversion module for video and audio files.

Handles HandBrakeCLI (video) and FFmpeg (audio) conversions.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import logging

from .config import Config
from .file_detector import MediaFile, MediaType

logger = logging.getLogger(__name__)


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
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> ConversionResult:
        """
        Convert a video file using HandBrakeCLI.
        
        Args:
            input_file: Input video file path
            output_file: Output video file path
            category: Category (radarr/tv-sonarr) to determine preset
            progress_callback: Optional callback for progress updates (percent, eta)
        
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
        
        # Build HandBrakeCLI command
        # Use --json for better progress parsing
        cmd = [
            Config.HANDBRAKE_CLI,
            "--input", str(input_file),
            "--output", str(output_file),
            "--preset", preset,
            "--json"  # JSON output for better progress parsing
        ]
        
        try:
            import time
            import json
            start_time = time.time()
            
            # Run HandBrakeCLI
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Parse JSON output for progress if callback provided
            if progress_callback:
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # HandBrake JSON output: {"Progress": {"PercentComplete": 45.23, ...}}
                        data = json.loads(line)
                        if "Progress" in data:
                            progress = data["Progress"]
                            percent = progress.get("PercentComplete", 0.0)
                            if percent > 0:
                                progress_callback(percent, "")
                    except (json.JSONDecodeError, KeyError, ValueError):
                        # Fallback: try to parse text output
                        if "Encoding:" in line and "%" in line:
                            try:
                                percent_str = line.split("%")[0].split()[-1]
                                percent = float(percent_str)
                                progress_callback(percent, "")
                            except (ValueError, IndexError):
                                pass
            
            process.wait()
            duration = time.time() - start_time
            
            if process.returncode == 0 and output_file.exists():
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size
                )
            else:
                return ConversionResult(
                    success=False,
                    error=f"HandBrakeCLI exited with code {process.returncode}",
                    duration_seconds=duration,
                    original_size=original_size
                )
        
        except Exception as e:
            return ConversionResult(
                success=False,
                error=f"Conversion failed: {str(e)}",
                original_size=original_size
            )


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
    def convert(
        cls,
        input_file: Path,
        output_file: Path,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> ConversionResult:
        """
        Convert an audio file using FFmpeg.
        
        For lossy formats (MP3, AAC, etc.), just copies the file.
        For lossless formats (FLAC, WAV, etc.), converts to MP3 320kbps.
        
        Args:
            input_file: Input audio file path
            output_file: Output audio file path
            progress_callback: Optional callback for progress updates
        
        Returns:
            ConversionResult object
        """
        if not cls.is_ffmpeg_available():
            return ConversionResult(
                success=False,
                error=f"FFmpeg not found. Is '{Config.FFMPEG_BIN}' installed?"
            )
        
        if not input_file.exists():
            return ConversionResult(
                success=False,
                error=f"Input file does not exist: {input_file}"
            )
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        original_size = input_file.stat().st_size
        
        # If lossy format, just copy (no re-encoding)
        if cls.is_lossy_format(input_file):
            try:
                import time
                import shutil as shutil_module
                start_time = time.time()
                
                shutil_module.copy2(input_file, output_file)
                duration = time.time() - start_time
                
                if progress_callback:
                    progress_callback(100.0, "")
                
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size
                )
            except Exception as e:
                return ConversionResult(
                    success=False,
                    error=f"Copy failed: {str(e)}",
                    original_size=original_size
                )
        
        # For lossless formats, convert to MP3 320kbps
        cmd = [
            Config.FFMPEG_BIN,
            "-i", str(input_file),
            "-codec:a", "libmp3lame",
            "-b:a", Config.AUDIO_TARGET_BITRATE,
            "-y",  # Overwrite output file
            str(output_file)
        ]
        
        try:
            import time
            start_time = time.time()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Parse FFmpeg output for progress if callback provided
            if progress_callback:
                for line in process.stderr:
                    # FFmpeg progress format: "time=00:01:23.45 bitrate=..."
                    if "time=" in line:
                        try:
                            # Extract time and calculate percentage (simplified)
                            # This is a basic implementation - could be improved
                            pass
                        except:
                            pass
            
            process.wait()
            duration = time.time() - start_time
            
            if process.returncode == 0 and output_file.exists():
                return ConversionResult(
                    success=True,
                    output_path=output_file,
                    duration_seconds=duration,
                    original_size=original_size
                )
            else:
                error_output = process.stderr.read() if process.stderr else "Unknown error"
                return ConversionResult(
                    success=False,
                    error=f"FFmpeg conversion failed: {error_output[:200]}",
                    duration_seconds=duration,
                    original_size=original_size
                )
        
        except Exception as e:
            return ConversionResult(
                success=False,
                error=f"Conversion failed: {str(e)}",
                original_size=original_size
            )


class MediaConverter:
    """Main converter class that routes to appropriate converter."""
    
    @classmethod
    def convert(
        cls,
        media_file: MediaFile,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> ConversionResult:
        """
        Convert a media file based on its type.
        
        Args:
            media_file: MediaFile object to convert
            output_path: Optional output path override
            progress_callback: Optional progress callback
        
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
                progress_callback
            )
        elif media_file.media_type == MediaType.AUDIO:
            return AudioConverter.convert(
                media_file.path,
                output_path,
                progress_callback
            )
        else:
            return ConversionResult(
                success=False,
                error=f"Unknown media type: {media_file.media_type}"
            )
