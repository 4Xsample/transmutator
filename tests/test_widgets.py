"""Tests for custom TUI widgets and helpers."""

import pytest

from src.widgets import (
    COL_W_DEFAULT,
    BRIGHT, MID, DIM, BAR_OK,
    _trunc,
    _esc,
    gradient,
    mini_bar,
    FileRow,
)
from src.hacker import generate_animation, QUOTES


# ── _trunc ───────────────────────────────────────────────────────────


class TestTrunc:
    def test_short_name_padded(self):
        assert len(_trunc("abc", 24)) == 24
        assert _trunc("abc", 24).startswith("abc")

    def test_exact_width(self):
        name = "a" * 30
        assert _trunc(name, 30) == name

    def test_long_name_truncated(self):
        t = _trunc("a" * 40, 24)
        assert len(t) == 24
        assert t.endswith("..")

    def test_dynamic_widths(self):
        """Truncation adapts to different widths."""
        for w in (10, 24, 50, 80):
            assert len(_trunc("x" * 100, w)) == w


# ── _esc ─────────────────────────────────────────────────────────────


class TestEsc:
    def test_no_brackets(self):
        assert _esc("hello") == "hello"

    def test_bracket_escaped(self):
        assert _esc("a[b") == "a\\[b"


# ── gradient ─────────────────────────────────────────────────────────


class TestGradient:
    def test_returns_str(self):
        assert isinstance(gradient("test.mkv", 50, source=True, width=24), str)

    def test_zero_pct_source_uses_bright(self):
        s = gradient("abcd", 0, source=True, width=24)
        assert BRIGHT in s

    def test_zero_pct_dest_uses_dim(self):
        s = gradient("abcd", 0, source=False, width=24)
        assert DIM in s

    def test_100_pct_source_uses_dim(self):
        s = gradient("abcd", 100, source=True, width=24)
        assert DIM in s

    def test_100_pct_dest_uses_bright(self):
        s = gradient("abcd", 100, source=False, width=24)
        assert BRIGHT in s

    def test_50_pct_has_mid(self):
        s = gradient("a" * 30, 50, source=True, width=30)
        assert MID in s

    def test_name_chars_present(self):
        name = "Show.S01E03"
        s = gradient(name, 43, source=True, width=24)
        assert "S" in s
        assert "E" in s

    def test_different_widths(self):
        """Gradient adapts to different column widths."""
        for w in (10, 24, 50):
            s = gradient("Movie.2024.1080p.mkv", 50, source=True, width=w)
            assert isinstance(s, str)
            assert MID in s


# ── mini_bar ─────────────────────────────────────────────────────────


class TestMiniBar:
    def test_returns_str(self):
        assert isinstance(mini_bar(50.0), str)

    def test_zero_pct(self):
        s = mini_bar(0.0)
        assert "0.0%" in s

    def test_100_pct(self):
        s = mini_bar(100.0)
        assert "100.0%" in s
        assert "█" in s

    def test_50_pct_mixed(self):
        s = mini_bar(50.0)
        assert "█" in s
        assert "░" in s


# ── FileRow ──────────────────────────────────────────────────────────


class TestFileRow:
    def test_defaults(self):
        r = FileRow("movie.mkv")
        assert r.name == "movie.mkv"
        assert r.status == "pending"
        assert r.progress == 0.0
        assert r.category == ""

    def test_custom_values(self):
        r = FileRow("ep.mkv", category="tv-sonarr", progress=50.0, status="active")
        assert r.category == "tv-sonarr"
        assert r.progress == 50.0


# ── hacker animation ─────────────────────────────────────────────────


class TestHackerAnimation:
    def test_returns_list(self):
        lines = generate_animation({"phase": "transform", "files_count": 5})
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_contains_technical_and_quote(self):
        lines = generate_animation(
            {"phase": "transform", "files_count": 10, "video_count": 7, "audio_count": 3},
            num_quotes=2,
        )
        has_quote = any("—" in l or '"' in l for l in lines)
        has_tech = any("10" in l for l in lines)
        assert has_quote
        assert has_tech

    def test_load_phase(self):
        lines = generate_animation({"phase": "load", "files_count": 3})
        has_plex = any("plex" in l.lower() or "rsync" in l.lower() for l in lines)
        assert has_plex

    def test_num_quotes_respected(self):
        lines = generate_animation({"phase": "transform", "files_count": 1}, num_quotes=1)
        quote_count = sum(1 for l in lines if "—" in l)
        assert quote_count >= 1

    def test_quotes_list_not_empty(self):
        assert len(QUOTES) >= 10

    def test_report_phase(self):
        lines = generate_animation(
            {"phase": "report", "ok_count": 5, "fail_count": 1, "space_saved": "1.2 GB"},
        )
        assert isinstance(lines, list)
        assert len(lines) > 0
        has_report = any("report" in l.lower() or "compilant" in l.lower() for l in lines)
        assert has_report
