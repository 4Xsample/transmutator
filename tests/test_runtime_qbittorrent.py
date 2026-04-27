from pathlib import Path

from src.file_detector import MediaFile, MediaType
from src.runtime_pipeline import PipelineRunner


def _media(path: str, category: str = "lidarr") -> MediaFile:
    return MediaFile(Path(path), MediaType.AUDIO, category)


def test_qbittorrent_batch_key_groups_album_tracks(monkeypatch):
    monkeypatch.setattr(
        "src.runtime_pipeline.Config.get_tmp_path",
        lambda category: Path(f"/tmp/TMP/{category}"),
    )
    runner = PipelineRunner()

    a = _media("/tmp/TMP/lidarr/Album/01. Track.flac")
    b = _media("/tmp/TMP/lidarr/Album/02. Track.flac")
    c = _media("/tmp/TMP/lidarr/Other Album/01. Track.flac")

    assert runner._qbittorrent_batch_key(a) == runner._qbittorrent_batch_key(b)
    assert runner._qbittorrent_batch_key(a) != runner._qbittorrent_batch_key(c)
