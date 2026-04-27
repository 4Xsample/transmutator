"""Tests for runtime pipeline helpers used by the Web UI."""

import time
from pathlib import Path

from src.file_detector import MediaFile, MediaType
from src.runtime_pipeline import PipelineRunner, scan_pipeline_files


def _media(path: str, category: str) -> MediaFile:
    return MediaFile(Path(path), MediaType.VIDEO, category)


class TestScanPipelineFiles:
    def test_prefers_torrent_rows_with_pending_or_done_state(self, monkeypatch):
        monkeypatch.setattr(
            "src.runtime_pipeline.FileDetector.scan_all_categories",
            lambda: {"radarr": [_media("/tmp/tmp/radarr/movie.mkv", "radarr")]},
        )
        monkeypatch.setattr(
            "src.runtime_pipeline.Config.get_tmp_path",
            lambda category: Path(f"/tmp/tmp/{category}"),
        )
        monkeypatch.setattr("src.runtime_pipeline.Config.TORRENT_BASE", Path("/tmp/torrent"))
        monkeypatch.setattr(
            "src.runtime_pipeline.FileDetector.scan_torrent_sources",
            lambda: {"radarr": [_media("/tmp/torrent/radarr/movie.mkv", "radarr")]},
        )
        monkeypatch.setattr(
            "src.runtime_pipeline.Config.get_torrent_path",
            lambda category: Path(f"/tmp/torrent/{category}"),
        )

        rows = scan_pipeline_files()

        assert rows == [
            {
                "id": "radarr:/tmp/tmp/radarr/movie.mkv",
                "path": "/tmp/tmp/radarr/movie.mkv",
                "name": "movie.mkv",
                "category": "radarr",
                "status": "done",
                "progress": 100.0,
            }
        ]

    def test_falls_back_to_tmp_only_when_torrent_scan_is_empty(self, monkeypatch):
        monkeypatch.setattr(
            "src.runtime_pipeline.FileDetector.scan_all_categories",
            lambda: {"lidarr": [MediaFile(Path("/tmp/tmp/lidarr/song.mp3"), MediaType.AUDIO, "lidarr")]},
        )
        monkeypatch.setattr("src.runtime_pipeline.Config.TORRENT_BASE", Path("/tmp/torrent"))
        monkeypatch.setattr(
            "src.runtime_pipeline.FileDetector.scan_torrent_sources",
            lambda: {},
        )

        rows = scan_pipeline_files()

        assert rows == [
            {
                "id": "lidarr:/tmp/tmp/lidarr/song.mp3",
                "path": "/tmp/tmp/lidarr/song.mp3",
                "name": "song.mp3",
                "category": "lidarr",
                "status": "done",
                "progress": 100.0,
            }
        ]


class TestPipelineRunner:
    def test_start_runs_to_completed_without_work(self, monkeypatch):
        monkeypatch.setattr("src.runtime_pipeline.scan_pipeline_files", lambda: [])
        monkeypatch.setattr("src.runtime_pipeline.get_pipeline_selection", lambda: {})
        monkeypatch.setattr("src.runtime_pipeline.FileDetector.scan_all_categories", lambda: {})

        runner = PipelineRunner()
        assert runner.start()

        deadline = time.time() + 2.0
        while time.time() < deadline:
            snap = runner.snapshot()
            if snap["pipeline"] in {"completed", "error", "stopped"}:
                break
            time.sleep(0.01)

        snap = runner.snapshot()
        assert snap["pipeline"] == "completed"
        assert snap["phase"] is None
        assert snap["results"]["ok"] == 0
        assert snap["results"]["fail"] == 0

    def test_rejects_second_start_while_running(self, monkeypatch):
        def slow_scan():
            time.sleep(0.2)
            return {}

        monkeypatch.setattr("src.runtime_pipeline.scan_pipeline_files", lambda: [])
        monkeypatch.setattr(
            "src.runtime_pipeline.get_pipeline_selection",
            lambda: {"radarr": {"importar": False, "convertir": True, "enviar": False}},
        )
        monkeypatch.setattr("src.runtime_pipeline.FileDetector.scan_all_categories", slow_scan)

        runner = PipelineRunner()
        assert runner.start()
        assert not runner.start()

    def test_report_history_and_payload_read_from_disk(self, tmp_path, monkeypatch):
        report_id = "transmutator_report_20260407_120000"
        report_path = tmp_path / f"{report_id}.json"
        report_path.write_text(
            """
            {
              "timestamp": "2026-04-07T12:00:00",
              "extract_done": 1,
              "extract_total": 1,
              "load_done": 1,
              "load_total": 1,
              "summary": {
                "total_results": 1,
                "successes": 1,
                "failures": 0,
                "success_rate": 100.0,
                "total_original_size": 100,
                "total_output_size": 80,
                "total_duration": 4,
                "space_saved": 20,
                "compression_ratio": 20.0
              },
              "results": [],
              "by_category": {},
              "media_types": {},
              "qbittorrent": {
                "enabled": false,
                "successes": 0,
                "failures": 0,
                "actions": []
              },
              "runtime": {
                "pipeline_state": "completed"
              }
            }
            """.strip(),
            encoding="utf-8",
        )

        runner = PipelineRunner()
        monkeypatch.setattr(runner, "_reports_dir", lambda: tmp_path)

        history = runner.report_history(limit=10)
        payload = runner.report_payload(report_id)

        assert len(history) == 1
        assert history[0]["id"] == report_id
        assert payload is not None
        assert payload["runtime"]["pipeline_state"] == "completed"

    def test_cleanup_converted_source_removes_file_and_empty_dirs(self, tmp_path, monkeypatch):
        category_root = tmp_path / "lidarr"
        album_dir = category_root / "Album"
        album_dir.mkdir(parents=True)
        source = album_dir / "01. Track.flac"
        source.write_text("x", encoding="utf-8")

        runner = PipelineRunner()
        monkeypatch.setattr("src.runtime_pipeline.Config.get_tmp_path", lambda category: category_root)

        runner._cleanup_converted_source(_media(str(source), "lidarr"))

        assert not source.exists()
        assert not album_dir.exists()

    def test_reorder_transform_queue_reorders_pending_rows(self, monkeypatch):
        runner = PipelineRunner()
        runner._phase = "transform"
        b = _media("/tmp/b.mkv", "radarr")
        c = _media("/tmp/c.mkv", "radarr")
        runner._convert_queue = [b, c]
        runner._files = [
            {"id": "done-row", "name": "a.mkv", "category": "radarr", "status": "done", "progress": 100.0},
            {"id": runner._row_id_for_media(b), "name": "b.mkv", "category": "radarr", "status": "pending", "progress": 0.0},
            {"id": runner._row_id_for_media(c), "name": "c.mkv", "category": "radarr", "status": "pending", "progress": 0.0},
        ]

        snap = runner.reorder_transform_queue([runner._row_id_for_media(c), runner._row_id_for_media(b)])

        assert [item.path.name for item in runner._convert_queue] == ["c.mkv", "b.mkv"]
        pending_names = [row["name"] for row in snap["files"] if row["status"] == "pending"]
        assert pending_names == ["c.mkv", "b.mkv"]
