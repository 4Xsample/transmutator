from pathlib import Path

from src.config import Config
from src.converter import MediaConverter
from src.file_detector import MediaFile, MediaType


def test_default_output_path_preserves_album_structure_for_audio(monkeypatch):
    monkeypatch.setattr(Config, "AUDIO_TARGET_FORMAT", "mp3")
    monkeypatch.setattr(Config, "AUDIO_LOSSLESS_EXTENSIONS", {".flac"})
    monkeypatch.setattr(Config, "get_tmp_path", lambda category: Path(f"/tmp/TMP/{category}"))
    monkeypatch.setattr(Config, "get_output_path", lambda category: Path("/tmp/Music"))

    media = MediaFile(
        path=Path("/tmp/TMP/lidarr/Guns N' Roses - Use Your Illusion II/01. Civil War.flac"),
        media_type=MediaType.AUDIO,
        category="lidarr",
    )

    output = MediaConverter._default_output_path(media)

    assert output == Path("/tmp/Music/Guns N' Roses - Use Your Illusion II/01. Civil War.mp3")


def test_default_output_path_keeps_filename_when_outside_tmp(monkeypatch):
    monkeypatch.setattr(Config, "AUDIO_TARGET_FORMAT", "mp3")
    monkeypatch.setattr(Config, "AUDIO_LOSSLESS_EXTENSIONS", {".flac"})
    monkeypatch.setattr(Config, "get_tmp_path", lambda category: Path(f"/tmp/TMP/{category}"))
    monkeypatch.setattr(Config, "get_output_path", lambda category: Path("/tmp/Music"))

    media = MediaFile(
        path=Path("/somewhere-else/track.flac"),
        media_type=MediaType.AUDIO,
        category="lidarr",
    )

    output = MediaConverter._default_output_path(media)

    assert output == Path("/tmp/Music/track.mp3")
