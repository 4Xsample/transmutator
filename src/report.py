"""
Report generation for Transmutator V2.

Provides structured report data, Rich-markup TUI rendering,
and Markdown export for pipeline execution results.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .converter import ConversionResult
from .file_detector import MediaFile
from .pipeline import format_size
from .widgets import BRIGHT, MID, DIM, BAR_OK, WARN, ERR, _esc, _trunc


# ── Report data ──────────────────────────────────────────────────────


class ReportData:
    """Structured report data from a pipeline execution."""

    def __init__(
        self,
        results: List[Tuple[MediaFile, ConversionResult]],
        extract_done: int = 0,
        extract_total: int = 0,
        load_done: int = 0,
        load_total: int = 0,
    ):
        self.results = results
        self.extract_done = extract_done
        self.extract_total = extract_total
        self.load_done = load_done
        self.load_total = load_total
        self.timestamp = datetime.now()

    @property
    def successes(self) -> List[Tuple[MediaFile, ConversionResult]]:
        return [(mf, cr) for mf, cr in self.results if cr.success]

    @property
    def failures(self) -> List[Tuple[MediaFile, ConversionResult]]:
        return [(mf, cr) for mf, cr in self.results if not cr.success]

    @property
    def total_original_size(self) -> int:
        return sum(cr.original_size or 0 for _, cr in self.results)

    @property
    def total_output_size(self) -> int:
        return sum(cr.output_size or 0 for _, cr in self.successes)

    @property
    def total_duration(self) -> float:
        return sum(cr.duration_seconds or 0 for _, cr in self.results)

    @property
    def space_saved(self) -> int:
        return max(0, self.total_original_size - self.total_output_size)

    @property
    def compression_ratio(self) -> float:
        if self.total_original_size == 0:
            return 0.0
        return (self.space_saved / self.total_original_size) * 100.0


# ── Helpers ──────────────────────────────────────────────────────────


def fmt_duration(seconds: Optional[float]) -> str:
    """Format seconds as a human-readable duration string."""
    if not seconds or seconds <= 0:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# ── TUI Rich-markup rendering ───────────────────────────────────────


def build_report_tui(data: ReportData, width: int = 80) -> str:
    """Build Rich-markup content for the TUI report screen.

    *width* is the usable content width (terminal minus borders/padding).
    All decorative elements adapt to this value.
    """
    ok = len(data.successes)
    fail = len(data.failures)
    total = len(data.results)

    # Inner content area: 2 char left margin ("  ") + 2 header box border
    # so box interior is width - 6.  Keep a minimum of 30.
    box_w = max(30, width - 6)
    rule_w = max(20, width - 4)
    # Name column gets roughly 40 % of available space, rest for info
    name_w = max(12, int(box_w * 0.4))
    err_w = max(10, box_w - name_w - 6)  # 6 = marker + spaces

    lines: list[str] = []

    # ── Header ──
    lines.append("")
    lines.append(f"  [bold {BRIGHT}]╔{'═' * box_w}╗[/]")
    lines.append(f"  [bold {BRIGHT}]║{'TRANSMUTATOR — REPORT FINAL':^{box_w}}║[/]")
    lines.append(f"  [bold {BRIGHT}]╚{'═' * box_w}╝[/]")
    lines.append("")

    # ── Phase summary ──
    if data.extract_total:
        e_col = BAR_OK if data.extract_done == data.extract_total else WARN
        lines.append(
            f"  [{BRIGHT}]EXTRACCIÓ :[/]  "
            f"[{e_col}]{data.extract_done}/{data.extract_total} fitxers importats[/]"
        )

    c_col = BAR_OK if fail == 0 else WARN
    lines.append(
        f"  [{BRIGHT}]CONVERSIÓ :[/]  "
        f"[{c_col}]{ok} èxits, {fail} errors de {total}[/]"
    )

    if data.load_total:
        l_col = BAR_OK if data.load_done == data.load_total else WARN
        lines.append(
            f"  [{BRIGHT}]CÀRREGA   :[/]  "
            f"[{l_col}]{data.load_done}/{data.load_total} fitxers enviats a Plex[/]"
        )
    lines.append("")

    # ── Successes ──
    if data.successes:
        lines.append(f"  [bold {BAR_OK}]✓ ÈXITS ({ok})[/]")
        lines.append(f"  [{DIM}]{'─' * rule_w}[/]")
        for mf, cr in data.successes:
            name = _esc(_trunc(mf.path.name, name_w))
            if cr.original_size and cr.output_size and cr.original_size > 0:
                orig = format_size(cr.original_size)
                out = format_size(cr.output_size)
                pct = (cr.original_size - cr.output_size) / cr.original_size * 100
                info = f"{orig} → {out}  {pct:+.0f}%"
            elif cr.original_size:
                info = format_size(cr.original_size)
            else:
                info = ""
            dur = fmt_duration(cr.duration_seconds)
            lines.append(
                f"  [{BAR_OK}]✓[/] [{BRIGHT}]{name}[/]  [{MID}]{info}[/]  [{DIM}]{dur}[/]"
            )
        lines.append("")

    # ── Errors ──
    if data.failures:
        lines.append(f"  [bold {ERR}]✗ ERRORS ({fail})[/]")
        lines.append(f"  [{DIM}]{'─' * rule_w}[/]")
        for mf, cr in data.failures:
            name = _esc(_trunc(mf.path.name, name_w))
            err = _esc(_trunc(cr.error or "Error desconegut", err_w))
            lines.append(
                f"  [{ERR}]✗[/] [{BRIGHT}]{name}[/]  [{WARN}]{err}[/]"
            )
        lines.append("")

    # ── No results ──
    if not data.results:
        lines.append(f"  [{DIM}]Cap fitxer processat.[/]")
        lines.append("")

    # ── Statistics ──
    lines.append(f"  [bold {BRIGHT}]⚡ ESTADÍSTIQUES[/]")
    lines.append(f"  [{DIM}]{'─' * rule_w}[/]")
    lines.append(
        f"  [{BRIGHT}]Temps total  :[/]  [{MID}]{fmt_duration(data.total_duration)}[/]"
    )
    lines.append(
        f"  [{BRIGHT}]Espai origen :[/]  [{MID}]{format_size(data.total_original_size)}[/]"
    )
    lines.append(
        f"  [{BRIGHT}]Espai final  :[/]  [{MID}]{format_size(data.total_output_size)}[/]"
    )

    saved = data.space_saved
    ratio = data.compression_ratio
    if saved > 0:
        lines.append(
            f"  [{BRIGHT}]Estalviat    :[/]  "
            f"[{BAR_OK}]{format_size(saved)} ({ratio:.1f}%)[/]"
        )
    else:
        lines.append(f"  [{BRIGHT}]Estalviat    :[/]  [{DIM}]—[/]")

    lines.append("")
    lines.append(f"  [{DIM}]{data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/]")
    lines.append(f"  [{DIM}]4Xsample Industries (tm) — Transmutator V2[/]")
    lines.append("")

    return "\n".join(lines)


# ── Markdown report generation ───────────────────────────────────────


def generate_report_markdown(data: ReportData) -> str:
    """Generate a Markdown-formatted pipeline report."""
    lines: list[str] = []
    ts = data.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# Transmutator V2 — Report de Pipeline")
    lines.append("")
    lines.append(f"**Data:** {ts}")
    lines.append(f"**Total fitxers processats:** {len(data.results)}")
    lines.append(
        f"**Èxits:** {len(data.successes)} | **Errors:** {len(data.failures)}"
    )
    if data.extract_total:
        lines.append(
            f"**Extracció:** {data.extract_done}/{data.extract_total} fitxers importats"
        )
    if data.load_total:
        lines.append(
            f"**Càrrega a Plex:** {data.load_done}/{data.load_total} fitxers enviats"
        )
    lines.append("")

    # ── Successes ──
    if data.successes:
        lines.append("## ✓ Èxits")
        lines.append("")
        lines.append("| Fitxer | Categoria | Original | Final | Estalvi | Temps |")
        lines.append("|--------|-----------|----------|-------|---------|-------|")
        for mf, cr in data.successes:
            orig = format_size(cr.original_size) if cr.original_size else "—"
            out = format_size(cr.output_size) if cr.output_size else "—"
            if cr.original_size and cr.output_size and cr.original_size > 0:
                saved = cr.original_size - cr.output_size
                pct = saved / cr.original_size * 100
                sav = f"{format_size(abs(saved))} ({pct:+.0f}%)"
            else:
                sav = "—"
            dur = fmt_duration(cr.duration_seconds)
            lines.append(
                f"| {mf.path.name} | {mf.category} | {orig} | {out} | {sav} | {dur} |"
            )
        lines.append("")

    # ── Failures ──
    if data.failures:
        lines.append("## ✗ Errors")
        lines.append("")
        lines.append("| Fitxer | Categoria | Error |")
        lines.append("|--------|-----------|-------|")
        for mf, cr in data.failures:
            err = (cr.error or "Error desconegut").replace("|", "\\|")[:120]
            lines.append(f"| {mf.path.name} | {mf.category} | {err} |")
        lines.append("")

    # ── Stats ──
    lines.append("## Estadístiques")
    lines.append("")
    lines.append(f"- **Temps total de conversió:** {fmt_duration(data.total_duration)}")
    lines.append(f"- **Espai original:** {format_size(data.total_original_size)}")
    lines.append(f"- **Espai final:** {format_size(data.total_output_size)}")
    lines.append(
        f"- **Espai estalviat:** {format_size(data.space_saved)} "
        f"({data.compression_ratio:.1f}%)"
    )
    lines.append("")
    lines.append("---")
    lines.append("*Generat per Transmutator V2 — 4Xsample Industries (tm)*")

    return "\n".join(lines)


# ── Save to file ─────────────────────────────────────────────────────


def save_report(data: ReportData, directory: Optional[Path] = None) -> Path:
    """Save the report as a Markdown file. Returns the file path."""
    if directory is None:
        directory = Path.home()
    directory.mkdir(parents=True, exist_ok=True)
    ts = data.timestamp.strftime("%Y%m%d_%H%M%S")
    filepath = directory / f"transmutator_report_{ts}.md"
    filepath.write_text(generate_report_markdown(data), encoding="utf-8")
    return filepath
