"""
File detection and classification module.

Detects media files and classifies them as Video or Audio.
"""

from pathlib import Path
from typing import List, Dict, Optional, Literal
from enum import Enum

from .config import Config


class MediaType(Enum):
    """Media type enumeration."""
    VIDEO = "video"
    AUDIO = "audio"
    UNKNOWN = "unknown"


class MediaFile:
    """Represents a detected media file."""
    
    def __init__(
        self,
        path: Path,
        media_type: MediaType,
        category: str,
        original_size: Optional[int] = None
    ):
        self.path = path
        self.media_type = media_type
        self.category = category
        self.original_size = original_size or self._get_file_size()
        self.processed = False
        self.error: Optional[str] = None
    
    def _get_file_size(self) -> int:
        """Get file size in bytes."""
        try:
            return self.path.stat().st_size
        except OSError:
            return 0
    
    def __repr__(self):
        return f"MediaFile(path={self.path}, type={self.media_type.value}, category={self.category})"


class FileDetector:
    """Detects and classifies media files."""
    
    @staticmethod
    def is_video_file(path: Path) -> bool:
        """Check if file is a video file."""
        return path.suffix.lower() in Config.VIDEO_EXTENSIONS
    
    @staticmethod
    def is_audio_file(path: Path) -> bool:
        """Check if file is an audio file."""
        return path.suffix.lower() in Config.AUDIO_EXTENSIONS
    
    @staticmethod
    def classify_file(path: Path) -> MediaType:
        """Classify a file as video, audio, or unknown."""
        if FileDetector.is_video_file(path):
            return MediaType.VIDEO
        elif FileDetector.is_audio_file(path):
            return MediaType.AUDIO
        else:
            return MediaType.UNKNOWN
    
    @staticmethod
    def detect_category(path: Path) -> Optional[str]:
        """Detect the category (tv-sonarr, radarr, lidarr) from path."""
        path_str = str(path)
        
        # Check for category indicators in path
        if "tv-sonarr" in path_str or "sonarr" in path_str.lower():
            return "tv-sonarr"
        elif "radarr" in path_str.lower():
            return "radarr"
        elif "lidarr" in path_str.lower():
            return "lidarr"
        
        return None
    
    @classmethod
    def scan_directory(
        cls,
        directory: Path,
        category: Optional[str] = None,
        recursive: bool = True
    ) -> List[MediaFile]:
        """
        Scan a directory for media files.
        
        Args:
            directory: Directory to scan
            category: Optional category override (tv-sonarr, radarr, lidarr)
            recursive: Whether to scan recursively
        
        Returns:
            List of detected MediaFile objects
        """
        media_files = []
        
        if not directory.exists():
            return media_files
        
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue
            
            # Classify file
            media_type = cls.classify_file(file_path)
            if media_type == MediaType.UNKNOWN:
                continue
            
            # Detect or use provided category
            detected_category = category or cls.detect_category(file_path)
            if not detected_category:
                # Default based on media type
                detected_category = "radarr" if media_type == MediaType.VIDEO else "lidarr"
            
            media_files.append(
                MediaFile(
                    path=file_path,
                    media_type=media_type,
                    category=detected_category
                )
            )
        
        return media_files
    
    @classmethod
    def scan_tmp_staging(cls, category: str) -> List[MediaFile]:
        """Scan the TMP staging directory for a specific category."""
        tmp_path = Config.get_tmp_path(category)
        return cls.scan_directory(tmp_path, category=category, recursive=True)
    
    @classmethod
    def scan_all_categories(cls) -> Dict[str, List[MediaFile]]:
        """Scan all category directories in TMP staging."""
        results = {}
        
        for category in Config.TORRENT_CATEGORIES.keys():
            files = cls.scan_tmp_staging(category)
            if files:
                results[category] = files
        
        return results

    @classmethod
    def scan_torrent_sources(cls) -> Dict[str, List[MediaFile]]:
        """Scan torrent source directories for all categories."""
        results = {}

        for category in Config.TORRENT_CATEGORIES.keys():
            src = Config.get_torrent_path(category)
            if src.exists():
                files = cls.scan_directory(src, category=category, recursive=True)
                if files:
                    results[category] = files

        return results
