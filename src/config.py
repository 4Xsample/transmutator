"""
Configuration module for Transmutator V2.

Loads configuration from config.yaml if present, falls back to defaults.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def _expand_path(path_str: str) -> Path:
    """Expand ~ and convert to Path."""
    return Path(os.path.expanduser(path_str))


def _load_config() -> Dict[str, Any]:
    """Load configuration from YAML file or return empty dict."""
    if not YAML_AVAILABLE:
        return {}
    
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


_CONFIG = _load_config()


class Config:
    """Configuration class that loads from YAML with defaults."""
    
    # Paths - Load from YAML or use defaults
    _paths = _CONFIG.get("paths", {})
    TORRENT_BASE = _expand_path(_paths.get("torrent_base", "/mnt/Torrent"))
    TMP_STAGING = _expand_path(_paths.get("tmp_staging", "~/Videos/TMP"))
    OUTPUT_BASE = _expand_path(_paths.get("output_base", "~/Videos"))
    PLEX_DESTINATION = _expand_path(_paths.get("plex_destination", "/mnt/PlexMedia/Downloads"))
    
    # Category mappings
    _categories = _CONFIG.get("categories", {})
    TORRENT_CATEGORIES = {
        "tv-sonarr": _categories.get("tv-sonarr", "tv-sonarr"),
        "radarr": _categories.get("radarr", "radarr"),
        "lidarr": _categories.get("lidarr", "lidarr"),
    }
    
    # qBittorrent API settings
    _qbt = _CONFIG.get("qbittorrent", {})
    QBITTORRENT_URL = _qbt.get("url", "http://localhost:8080")
    QBITTORRENT_USERNAME = _qbt.get("username", "")
    QBITTORRENT_PASSWORD = _qbt.get("password", "")
    QBITTORRENT_API_KEY = ""  # Will be fetched on connection
    PROCESSED_CATEGORY = _qbt.get("processed_category", "processat")
    
    # Video settings
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm"}
    _video = _CONFIG.get("video", {})
    VIDEO_PRESET_MOVIES = _video.get("preset_movies", "4Xmovie")
    VIDEO_PRESET_SERIES = _video.get("preset_series", "4Xseries")
    VIDEO_TARGET_RESOLUTION = _video.get("target_resolution", "1080p")
    
    # Audio settings
    AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".aiff", ".m4a", ".aac"}
    AUDIO_LOSSY_EXTENSIONS = {".mp3", ".aac", ".ogg", ".m4a"}
    AUDIO_LOSSLESS_EXTENSIONS = {".flac", ".wav", ".aiff"}
    _audio = _CONFIG.get("audio", {})
    AUDIO_TARGET_BITRATE = _audio.get("target_bitrate", "320k")
    AUDIO_TARGET_FORMAT = _audio.get("target_format", "mp3")
    
    # HandBrake settings
    _tools = _CONFIG.get("tools", {})
    HANDBRAKE_CLI = _tools.get("handbrake_cli", "HandBrakeCLI")
    _presets_path = _tools.get("handbrake_presets_path", "~/.config/ghb/presets.json")
    HANDBRAKE_PRESETS_PATH = _expand_path(_presets_path)
    
    # FFmpeg settings
    FFMPEG_BIN = _tools.get("ffmpeg", "ffmpeg")
    
    @classmethod
    def get_torrent_path(cls, category: str) -> Path:
        """Get the torrent source path for a category."""
        return cls.TORRENT_BASE / category
    
    @classmethod
    def get_tmp_path(cls, category: str) -> Path:
        """Get the temporary staging path for a category."""
        return cls.TMP_STAGING / category
    
    @classmethod
    def get_output_path(cls, category: str) -> Path:
        """Get the output path for processed files."""
        if category == "lidarr":
            return cls.OUTPUT_BASE.parent / "Music"
        elif category == "radarr":
            return cls.OUTPUT_BASE / "radarr"
        elif category == "tv-sonarr":
            return cls.OUTPUT_BASE / "sonarr"
        else:
            return cls.OUTPUT_BASE / category
    
    @classmethod
    def get_plex_path(cls, category: str) -> Path:
        """Get the final Plex destination path."""
        if category == "lidarr":
            return cls.PLEX_DESTINATION / "Music"
        else:
            return cls.PLEX_DESTINATION
    
    @classmethod
    def validate_paths(cls) -> Dict[str, bool]:
        """Validate that all configured paths exist or can be created."""
        results = {}
        
        # Check if base paths exist
        results["torrent_base"] = cls.TORRENT_BASE.exists()
        results["tmp_staging"] = cls.TMP_STAGING.exists() or cls.TMP_STAGING.parent.exists()
        results["plex_destination"] = cls.PLEX_DESTINATION.exists()
        
        # Check if tools are available
        import shutil
        results["handbrake_available"] = shutil.which(cls.HANDBRAKE_CLI) is not None
        results["ffmpeg_available"] = shutil.which(cls.FFMPEG_BIN) is not None
        
        return results
