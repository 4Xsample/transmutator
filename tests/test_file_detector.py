"""
Tests for file detection and classification.
"""

import tempfile
from pathlib import Path
from src.file_detector import FileDetector, MediaType, MediaFile


def test_is_video_file():
    """Test video file detection."""
    assert FileDetector.is_video_file(Path("test.mkv"))
    assert FileDetector.is_video_file(Path("test.mp4"))
    assert not FileDetector.is_video_file(Path("test.mp3"))
    assert not FileDetector.is_video_file(Path("test.txt"))


def test_is_audio_file():
    """Test audio file detection."""
    assert FileDetector.is_audio_file(Path("test.mp3"))
    assert FileDetector.is_audio_file(Path("test.flac"))
    assert not FileDetector.is_audio_file(Path("test.mkv"))
    assert not FileDetector.is_audio_file(Path("test.txt"))


def test_classify_file():
    """Test file classification."""
    assert FileDetector.classify_file(Path("test.mkv")) == MediaType.VIDEO
    assert FileDetector.classify_file(Path("test.mp3")) == MediaType.AUDIO
    assert FileDetector.classify_file(Path("test.txt")) == MediaType.UNKNOWN


def test_detect_category():
    """Test category detection from path."""
    assert FileDetector.detect_category(Path("/mnt/Torrent/tv-sonarr/episode.mkv")) == "tv-sonarr"
    assert FileDetector.detect_category(Path("/mnt/Torrent/radarr/movie.mp4")) == "radarr"
    assert FileDetector.detect_category(Path("/mnt/Torrent/lidarr/album.flac")) == "lidarr"
