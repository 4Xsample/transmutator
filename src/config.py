"""
Configuration module for Transmutator V2.

Initially uses hardcoded values, will be migrated to JSON/YAML later.
"""

import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration class with hardcoded paths and settings."""
    
    # Paths - Hardcoded for now
    TORRENT_BASE = Path("/mnt/Torrent")
    TMP_STAGING = Path.home() / "Videos" / "TMP"
    OUTPUT_BASE = Path.home() / "Videos"
    PLEX_DESTINATION = Path("/mnt/PlexMedia/Downloads")
    
    # Category mappings
    TORRENT_CATEGORIES = {
        "tv-sonarr": "tv-sonarr",
        "radarr": "radarr",
        "lidarr": "lidarr",
    }
    
    # qBittorrent API settings (hardcoded for now)
    QBITTORRENT_URL = "http://localhost:8080"
    QBITTORRENT_USERNAME = ""  # Empty if no auth
    QBITTORRENT_PASSWORD = ""  # Empty if no auth
    QBITTORRENT_API_KEY = ""  # Will be fetched on connection
    
    # Processing category name
    PROCESSED_CATEGORY = "processat"
    
    # Video settings
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm"}
    VIDEO_PRESET_MOVIES = "4Xmovie"
    VIDEO_PRESET_SERIES = "4Xseries"
    VIDEO_TARGET_RESOLUTION = "1080p"
    
    # Audio settings
    AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".aiff", ".m4a", ".aac"}
    AUDIO_LOSSY_EXTENSIONS = {".mp3", ".aac", ".ogg", ".m4a"}
    AUDIO_LOSSLESS_EXTENSIONS = {".flac", ".wav", ".aiff"}
    AUDIO_TARGET_BITRATE = "320k"
    AUDIO_TARGET_FORMAT = "mp3"
    
    # HandBrake settings
    HANDBRAKE_CLI = "HandBrakeCLI"
    HANDBRAKE_PRESETS_PATH = Path.home() / ".config" / "ghb" / "presets.json"
    
    # FFmpeg settings
    FFMPEG_BIN = "ffmpeg"
    
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
