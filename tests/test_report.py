"""Tests for report generation (ReportData, TUI rendering, Markdown export)."""

from pathlib import Path

import pytest

from src.converter import ConversionResult
from src.file_detector import MediaFile, MediaType
from src.report import (
    ReportData,
    build_report_tui,
    fmt_duration,
    generate_report_markdown,
    save_report,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _mf(name: str, category: str = "radarr", mtype: MediaType = MediaType.VIDEO) -> MediaFile:
    """Create a stub MediaFile (path doesn't need to exist for tests)."""
    return MediaFile(path=Path(f"/tmp/{name}"), media_type=mtype, category=category, original_size=0)


def _cr(success: bool, orig: int = 0, out: int = 0, dur: float = 0, error: str = "") -> ConversionResult:
    """Create a stub ConversionResult."""
    return ConversionResult(
        success=success,
        output_path=None,
        error=error or None,
        duration_seconds=dur,
        original_size=orig,
        output_size=out,
    )


def _sample_results():
    """3 successes + 1 failure."""
    return [
        (_mf("Movie.2024.mkv"), _cr(True, orig=2_000_000_000, out=1_200_000_000, dur=300)),
        (_mf("Show.S01E01.mkv", "tv-sonarr"), _cr(True, orig=900_000_000, out=500_000_000, dur=120)),
        (_mf("album.flac", "lidarr", MediaType.AUDIO), _cr(True, orig=50_000_000, out=8_000_000, dur=5)),
        (_mf("Broken.mkv"), _cr(False, orig=1_000_000_000, error="HandBrakeCLI: exit 1")),
    ]


# ── fmt_duration ─────────────────────────────────────────────────────


class TestFmtDuration:
    def test_none(self):
        assert fmt_duration(None) == "—"

    def test_zero(self):
        assert fmt_duration(0) == "—"

    def test_negative(self):
        assert fmt_duration(-10) == "—"

    def test_seconds_only(self):
        assert fmt_duration(45) == "45s"

    def test_minutes_seconds(self):
        assert fmt_duration(125) == "2m 05s"

    def test_hours(self):
        assert fmt_duration(3661) == "1h 01m 01s"


# ── ReportData properties ───────────────────────────────────────────


class TestReportData:
    def test_empty(self):
        rd = ReportData(results=[])
        assert rd.successes == []
        assert rd.failures == []
        assert rd.total_original_size == 0
        assert rd.total_output_size == 0
        assert rd.total_duration == 0
        assert rd.space_saved == 0
        assert rd.compression_ratio == 0.0

    def test_successes_and_failures(self):
        rd = ReportData(results=_sample_results())
        assert len(rd.successes) == 3
        assert len(rd.failures) == 1

    def test_total_original_size(self):
        rd = ReportData(results=_sample_results())
        expected = 2_000_000_000 + 900_000_000 + 50_000_000 + 1_000_000_000
        assert rd.total_original_size == expected

    def test_total_output_size_only_successes(self):
        rd = ReportData(results=_sample_results())
        expected = 1_200_000_000 + 500_000_000 + 8_000_000
        assert rd.total_output_size == expected

    def test_total_duration(self):
        rd = ReportData(results=_sample_results())
        assert rd.total_duration == 300 + 120 + 5  # failure has dur=0

    def test_space_saved(self):
        rd = ReportData(results=_sample_results())
        orig = 2_000_000_000 + 900_000_000 + 50_000_000 + 1_000_000_000
        out = 1_200_000_000 + 500_000_000 + 8_000_000
        assert rd.space_saved == max(0, orig - out)

    def test_compression_ratio(self):
        rd = ReportData(results=_sample_results())
        assert 0 < rd.compression_ratio < 100

    def test_extract_load_counters(self):
        rd = ReportData(
            results=_sample_results(),
            extract_done=5, extract_total=5,
            load_done=3, load_total=3,
        )
        assert rd.extract_done == 5
        assert rd.load_total == 3

    def test_timestamp_set(self):
        rd = ReportData(results=[])
        assert rd.timestamp is not None


# ── build_report_tui ─────────────────────────────────────────────────


class TestBuildReportTui:
    def test_returns_string(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert isinstance(tui, str)
        assert len(tui) > 0

    def test_contains_header(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert "REPORT FINAL" in tui

    def test_contains_successes(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert "ÈXITS" in tui
        assert "Movie.2024.mkv" in tui

    def test_contains_errors(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert "ERRORS" in tui
        assert "Broken.mkv" in tui

    def test_contains_stats(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert "ESTADÍSTIQUES" in tui

    def test_empty_results(self):
        rd = ReportData(results=[])
        tui = build_report_tui(rd)
        assert "Cap fitxer processat" in tui

    def test_all_success(self):
        results = [
            (_mf("ok.mkv"), _cr(True, orig=1000, out=500, dur=10)),
        ]
        rd = ReportData(results=results)
        tui = build_report_tui(rd)
        assert "ÈXITS" in tui
        assert "ERRORS" not in tui

    def test_all_failures(self):
        results = [
            (_mf("fail.mkv"), _cr(False, error="boom")),
        ]
        rd = ReportData(results=results)
        tui = build_report_tui(rd)
        assert "ERRORS" in tui

    def test_extract_load_shown(self):
        rd = ReportData(
            results=_sample_results(),
            extract_done=5, extract_total=5,
            load_done=3, load_total=3,
        )
        tui = build_report_tui(rd)
        assert "EXTRACCIÓ" in tui
        assert "CÀRREGA" in tui

    def test_no_extract_load_when_zero(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd)
        assert "EXTRACCIÓ" not in tui
        assert "CÀRREGA" not in tui

    def test_adapts_to_narrow_width(self):
        rd = ReportData(results=_sample_results())
        narrow = build_report_tui(rd, width=50)
        wide = build_report_tui(rd, width=140)
        assert isinstance(narrow, str)
        assert isinstance(wide, str)
        # The box header should be wider in the wide version
        assert narrow.count("═") < wide.count("═")

    def test_very_narrow_does_not_crash(self):
        rd = ReportData(results=_sample_results())
        tui = build_report_tui(rd, width=30)
        assert "REPORT FINAL" in tui


# ── generate_report_markdown ─────────────────────────────────────────


class TestGenerateReportMarkdown:
    def test_returns_string(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert isinstance(md, str)

    def test_contains_header(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert "# Transmutator V2" in md

    def test_contains_table(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert "| Fitxer |" in md
        assert "Movie.2024.mkv" in md

    def test_contains_errors(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert "Errors" in md
        assert "Broken.mkv" in md

    def test_contains_stats(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert "Estadístiques" in md
        assert "Espai estalviat" in md

    def test_empty_results(self):
        rd = ReportData(results=[])
        md = generate_report_markdown(rd)
        assert "Total fitxers processats:** 0" in md

    def test_footer(self):
        rd = ReportData(results=_sample_results())
        md = generate_report_markdown(rd)
        assert "4Xsample Industries" in md

    def test_extract_load_shown(self):
        rd = ReportData(
            results=_sample_results(),
            extract_done=5, extract_total=5,
            load_done=3, load_total=3,
        )
        md = generate_report_markdown(rd)
        assert "Extracció" in md
        assert "Càrrega a Plex" in md


# ── save_report ──────────────────────────────────────────────────────


class TestSaveReport:
    def test_creates_file(self, tmp_path):
        rd = ReportData(results=_sample_results())
        filepath = save_report(rd, directory=tmp_path)
        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert filepath.parent == tmp_path

    def test_filename_has_timestamp(self, tmp_path):
        rd = ReportData(results=_sample_results())
        filepath = save_report(rd, directory=tmp_path)
        assert "transmutator_report_" in filepath.name

    def test_content_is_markdown(self, tmp_path):
        rd = ReportData(results=_sample_results())
        filepath = save_report(rd, directory=tmp_path)
        content = filepath.read_text(encoding="utf-8")
        assert "# Transmutator V2" in content

    def test_creates_directory_if_missing(self, tmp_path):
        target = tmp_path / "subdir" / "reports"
        rd = ReportData(results=[])
        filepath = save_report(rd, directory=target)
        assert filepath.exists()

    def test_empty_results_still_saves(self, tmp_path):
        rd = ReportData(results=[])
        filepath = save_report(rd, directory=tmp_path)
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert len(content) > 50
