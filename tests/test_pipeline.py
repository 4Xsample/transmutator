"""Tests for pipeline phases (Extract / Load) and utilities."""

import os
import time
from pathlib import Path
from typing import List, Tuple

import pytest

from src.pipeline import (
    PipelinePhase,
    ExtractPhase,
    LoadPhase,
    check_disk_space,
    format_size,
)
from src.config import Config


# ── format_size ──────────────────────────────────────────────────────


class TestFormatSize:
    def test_zero(self):
        assert format_size(0) == "0.0 B"

    def test_bytes(self):
        assert format_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_size(1024 ** 2) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 ** 3) == "1.0 GB"

    def test_terabytes(self):
        assert format_size(1024 ** 4) == "1.0 TB"

    def test_fractional_kb(self):
        result = format_size(1536)  # 1.5 KB
        assert "KB" in result
        assert result.startswith("1.5")


# ── check_disk_space ─────────────────────────────────────────────────


class TestCheckDiskSpace:
    def test_existing_dir(self, tmp_path):
        ok, avail = check_disk_space(tmp_path)
        assert avail > 0

    def test_nonexistent_uses_parent(self, tmp_path):
        ok, avail = check_disk_space(tmp_path / "does_not_exist")
        assert avail > 0

    def test_returns_tuple_of_two(self, tmp_path):
        result = check_disk_space(tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2


# ── PipelinePhase ────────────────────────────────────────────────────


class TestPipelinePhase:
    def test_success_defaults(self):
        p = PipelinePhase(success=True)
        assert p.success
        assert p.files_transferred == 0
        assert p.error == ""

    def test_success_with_count(self):
        p = PipelinePhase(success=True, files_transferred=7)
        assert p.files_transferred == 7

    def test_failure(self):
        p = PipelinePhase(success=False, error="disk full")
        assert not p.success
        assert p.error == "disk full"


# ── ExtractPhase._shutil ────────────────────────────────────────────


class TestExtractShutil:
    def test_copies_flat(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "movie.mkv").write_bytes(b"video")

        result = ExtractPhase._shutil(src, dst, "radarr", None)

        assert result.success
        assert result.files_transferred == 1
        assert (dst / "movie.mkv").read_bytes() == b"video"

    def test_copies_recursive(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "a").mkdir()
        (src / "a" / "ep.mkv").write_bytes(b"ep")
        (src / "b").mkdir()
        (src / "b" / "song.flac").write_bytes(b"audio")

        result = ExtractPhase._shutil(src, dst, "radarr", None)

        assert result.success
        assert result.files_transferred == 2
        assert (dst / "a" / "ep.mkv").exists()
        assert (dst / "b" / "song.flac").exists()

    def test_skips_up_to_date(self, tmp_path):
        """Files with older-or-equal mtime in source are skipped."""
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "f.mkv").write_bytes(b"data")
        (dst / "f.mkv").write_bytes(b"data")
        # Make destination newer
        st = (src / "f.mkv").stat()
        os.utime(dst / "f.mkv", (st.st_mtime + 1, st.st_mtime + 1))

        result = ExtractPhase._shutil(src, dst, "radarr", None)
        assert result.success
        assert result.files_transferred == 0

    def test_copies_when_source_newer(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (dst / "f.mkv").write_bytes(b"old")
        time.sleep(0.05)
        (src / "f.mkv").write_bytes(b"new")

        result = ExtractPhase._shutil(src, dst, "radarr", None)
        assert result.success
        assert result.files_transferred == 1
        assert (dst / "f.mkv").read_bytes() == b"new"

    def test_callback_invoked(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "a.mkv").write_bytes(b"a")

        events: List[Tuple[str, str, float]] = []
        def cb(cat, fname, pct):
            events.append((cat, fname, pct))

        ExtractPhase._shutil(src, dst, "radarr", cb)

        # Expect start (0%) and done (100%) for one file
        assert len(events) == 2
        assert events[0][2] == 0.0
        assert events[1][2] == 100.0
        assert events[0][0] == "radarr"

    def test_empty_source(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()

        result = ExtractPhase._shutil(src, dst, "radarr", None)
        assert result.success
        assert result.files_transferred == 0


# ── LoadPhase._shutil ───────────────────────────────────────────────


class TestLoadShutil:
    def test_moves_files(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "movie.mkv").write_bytes(b"video")
        (src / "sub").mkdir()
        (src / "sub" / "ep.mkv").write_bytes(b"ep")

        result = LoadPhase._shutil(src, dst, "radarr", None)

        assert result.success
        assert result.files_transferred == 2
        assert (dst / "movie.mkv").exists()
        assert (dst / "sub" / "ep.mkv").exists()
        # originals must be gone
        assert not (src / "movie.mkv").exists()
        assert not (src / "sub" / "ep.mkv").exists()

    def test_callback_invoked(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()
        (src / "song.mp3").write_bytes(b"audio")

        events: List[Tuple[str, str, float]] = []
        def cb(cat, fname, pct):
            events.append((cat, fname, pct))

        LoadPhase._shutil(src, dst, "radarr", cb)

        assert len(events) == 2
        assert events[0][2] == 0.0
        assert events[1][2] == 100.0

    def test_empty_source(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        src.mkdir(); dst.mkdir()

        result = LoadPhase._shutil(src, dst, "radarr", None)
        assert result.success
        assert result.files_transferred == 0


# ── Category-level wrappers (with monkeypatched Config) ──────────────


class TestExtractCategory:
    def test_missing_source_returns_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "get_torrent_path", lambda c: tmp_path / "nope")
        monkeypatch.setattr(Config, "get_tmp_path", lambda c: tmp_path / "tmp")

        result = ExtractPhase.extract_category("radarr")
        assert result.success
        assert result.files_transferred == 0

    def test_shutil_fallback(self, tmp_path, monkeypatch):
        """Force shutil path by hiding rsync."""
        src = tmp_path / "torrents"
        dst = tmp_path / "tmp"
        src.mkdir()
        (src / "movie.mkv").write_bytes(b"data")

        monkeypatch.setattr(Config, "get_torrent_path", lambda c: src)
        monkeypatch.setattr(Config, "get_tmp_path", lambda c: dst)
        monkeypatch.setattr(ExtractPhase, "_rsync_ok", staticmethod(lambda: False))

        result = ExtractPhase.extract_category("radarr")
        assert result.success
        assert result.files_transferred == 1
        assert (dst / "movie.mkv").exists()


class TestLoadCategory:
    def test_missing_source_returns_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "get_output_path", lambda c: tmp_path / "nope")

        result = LoadPhase.load_category("radarr")
        assert result.success
        assert result.files_transferred == 0

    def test_empty_dir_returns_success(self, tmp_path, monkeypatch):
        out = tmp_path / "output"
        out.mkdir()
        monkeypatch.setattr(Config, "get_output_path", lambda c: out)
        monkeypatch.setattr(Config, "get_plex_path", lambda c: tmp_path / "plex")

        result = LoadPhase.load_category("radarr")
        assert result.success
        assert result.files_transferred == 0

    def test_shutil_fallback(self, tmp_path, monkeypatch):
        out = tmp_path / "output"
        plex = tmp_path / "plex"
        out.mkdir()
        (out / "movie.mkv").write_bytes(b"data")

        monkeypatch.setattr(Config, "get_output_path", lambda c: out)
        monkeypatch.setattr(Config, "get_plex_path", lambda c: plex)
        monkeypatch.setattr(LoadPhase, "_rsync_ok", staticmethod(lambda: False))

        result = LoadPhase.load_category("radarr")
        assert result.success
        assert result.files_transferred == 1
        assert (plex / "movie.mkv").exists()
        assert not (out / "movie.mkv").exists()


# ── extract_all / load_all ───────────────────────────────────────────


class TestExtractAll:
    def test_all_missing_sources(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "get_torrent_path", lambda c: tmp_path / "nope")
        monkeypatch.setattr(Config, "get_tmp_path", lambda c: tmp_path / "tmp")

        result = ExtractPhase.extract_all()
        assert result.success
        assert result.files_transferred == 0


class TestLoadAll:
    def test_all_missing_sources(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "get_output_path", lambda c: tmp_path / "nope")

        result = LoadPhase.load_all()
        assert result.success
        assert result.files_transferred == 0
