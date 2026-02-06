"""
Custom TUI widgets for Transmutator V2.

DualColumnList  – dual-column file list with per-letter gradient
SegmentedBar    – three-phase progress indicator
CountdownScreen – modal popup with summary + countdown

Column widths are **dynamic**: they adapt to the terminal width.
"""

from __future__ import annotations

from typing import List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Static


# ── Pip-Boy colour palette ───────────────────────────────────────────

BRIGHT = "#4AEF98"
MID = "#2d8a4e"
DIM = "#1a3a1a"
BAR_OK = "#39FF14"
WARN = "#FFFF33"
ERR = "#D41227"

COL_W_DEFAULT = 24    # fallback when size unknown
SEP = " │ "           # column separator (3 chars)
MARKER_W = 2          # "▸ " or "  "


# ── Helpers ──────────────────────────────────────────────────────────


def _esc(s: str) -> str:
    """Escape Rich markup brackets in arbitrary text."""
    return s.replace("[", "\\[")


def _trunc(name: str, width: int) -> str:
    """Truncate *name* to *width*, padding with spaces if shorter."""
    if len(name) <= width:
        return name.ljust(width)
    return name[: width - 2] + ".."


def gradient(name: str, pct: float, *, source: bool, width: int = COL_W_DEFAULT) -> str:
    """Per-letter colour gradient for a file transfer (Rich markup)."""
    disp = _trunc(name, width)
    n = len(disp)

    if pct <= 0:
        c = BRIGHT if source else DIM
        return f"[{c}]{_esc(disp)}[/{c}]"
    if pct >= 100:
        c = DIM if source else BRIGHT
        return f"[{c}]{_esc(disp)}[/{c}]"

    cut = max(0, min(n - 1, int(n * pct / 100.0)))
    p1 = _esc(disp[:cut])
    pm = _esc(disp[cut])
    p2 = _esc(disp[cut + 1:]) if cut + 1 < n else ""

    parts: list[str] = []
    if source:
        if p1:
            parts.append(f"[{DIM}]{p1}[/{DIM}]")
        parts.append(f"[{MID}]{pm}[/{MID}]")
        if p2:
            parts.append(f"[{BRIGHT}]{p2}[/{BRIGHT}]")
    else:
        if p1:
            parts.append(f"[{BRIGHT}]{p1}[/{BRIGHT}]")
        parts.append(f"[{MID}]{pm}[/{MID}]")
        if p2:
            parts.append(f"[{DIM}]{p2}[/{DIM}]")
    return "".join(parts)


def mini_bar(pct: float, bar_width: int = COL_W_DEFAULT) -> str:
    """Text progress bar (Rich markup).  Total width = bar_width + 7."""
    bw = max(4, bar_width)
    filled = max(0, min(bw, int(bw * pct / 100.0)))
    parts: list[str] = []
    if filled:
        parts.append(f"[{BAR_OK}]{'█' * filled}[/{BAR_OK}]")
    rest = bw - filled
    if rest:
        parts.append(f"[{DIM}]{'░' * rest}[/{DIM}]")
    parts.append(f"[{BRIGHT}] {pct:5.1f}%[/{BRIGHT}]")
    return "".join(parts)


# ── FileRow ──────────────────────────────────────────────────────────


class FileRow:
    __slots__ = ("name", "category", "progress", "status", "error")

    def __init__(
        self,
        name: str,
        category: str = "",
        progress: float = 0.0,
        status: str = "pending",
        error: str = "",
    ):
        self.name = name
        self.category = category
        self.progress = progress
        self.status = status
        self.error = error


# ── DualColumnList ───────────────────────────────────────────────────


class DualColumnList(Static):
    """Dual-column file list with dynamic column widths."""

    def __init__(self, **kw):
        super().__init__("", markup=True, **kw)
        self._rows: List[FileRow] = []
        self._mode = "initial"
        self._sel = -1
        self._lh = "ORIGEN"
        self._rh = "DESTÍ"

    # -- dynamic column width ------------------------------------------

    @property
    def _cw(self) -> int:
        """Column width derived from the widget's current width."""
        w = self.size.width if self.size.width > 0 else 80
        # layout: marker(2) + left_col + sep(3) + right_col
        return max(10, (w - MARKER_W - len(SEP)) // 2)

    def on_resize(self, event) -> None:
        self._paint()

    # -- public API ----------------------------------------------------

    def set_mode(self, mode: str, left: str = "", right: str = ""):
        self._mode = mode
        if left:
            self._lh = left
        if right:
            self._rh = right
        self._paint()

    def set_rows(self, rows: List[FileRow]):
        self._rows = list(rows)
        self._paint()

    def update_row(self, idx: int, *, pct: float | None = None, status: str | None = None):
        if 0 <= idx < len(self._rows):
            if pct is not None:
                self._rows[idx].progress = pct
            if status is not None:
                self._rows[idx].status = status
            self._paint()

    def set_selected(self, idx: int):
        self._sel = idx
        self._paint()

    @property
    def rows(self) -> List[FileRow]:
        return self._rows

    # -- internal ------------------------------------------------------

    def _paint(self):
        render = {
            "transfer": self._r_transfer,
            "convert": self._r_convert,
        }.get(self._mode, self._r_initial)
        self.update(render())

    def _header(self) -> str:
        cw = self._cw
        lh = _esc(self._lh.center(cw))
        rh = _esc(self._rh.center(cw))
        line1 = (
            f"  [bold {BRIGHT}]{lh}[/bold {BRIGHT}]"
            f"[{DIM}]{SEP}[/{DIM}]"
            f"[bold {BRIGHT}]{rh}[/bold {BRIGHT}]"
        )
        dash = "─" * cw
        line2 = f"  [{DIM}]{dash}─┼─{dash}[/{DIM}]"
        return f"{line1}\n{line2}"

    # ---- transfer mode -----------------------------------------------

    def _r_transfer(self) -> str:
        cw = self._cw
        lines = [self._header()]
        sep = f"[{DIM}]{SEP}[/{DIM}]"
        for i, r in enumerate(self._rows):
            mk = "▸ " if i == self._sel else "  "
            if r.status == "done":
                left = f"[{DIM}]{_esc(_trunc(r.name, cw))}[/{DIM}]"
                right = f"[{BRIGHT}]{_esc(_trunc(r.name, cw))}[/{BRIGHT}]"
                lines.append(f"[{BAR_OK}]{_esc(mk)}[/{BAR_OK}]{left}{sep}{right}")
            elif r.status == "active":
                left = gradient(r.name, r.progress, source=True, width=cw)
                right = gradient(r.name, r.progress, source=False, width=cw)
                lines.append(f"[{WARN}]{_esc(mk)}[/{WARN}]{left}{sep}{right}")
            elif r.status == "error":
                nm = _esc(_trunc(r.name, cw))
                err = _esc("[ERROR]".center(cw))
                lines.append(f"[{ERR}]{_esc(mk)}{nm}[/{ERR}]{sep}[{ERR}]{err}[/{ERR}]")
            else:
                nm = _esc(_trunc(r.name, cw))
                lines.append(f"[{BRIGHT}]{_esc(mk)}{nm}[/{BRIGHT}]{sep}{' ' * cw}")
        return "\n".join(lines)

    # ---- convert mode ------------------------------------------------

    def _r_convert(self) -> str:
        cw = self._cw
        bw = max(4, cw - 7)  # bar chars; 7 = " xxx.x%"
        lines = [self._header()]
        sep = f"[{DIM}]{SEP}[/{DIM}]"
        for i, r in enumerate(self._rows):
            mk = "▸ " if i == self._sel else "  "
            nm = _esc(_trunc(r.name, cw))
            if r.status == "done":
                bar = mini_bar(100.0, bw)
                lines.append(f"[{BAR_OK}]{_esc(mk)}{nm}[/{BAR_OK}]{sep}{bar}")
            elif r.status == "active":
                bar = mini_bar(r.progress, bw)
                lines.append(f"[{WARN}]{_esc(mk)}{nm}[/{WARN}]{sep}{bar}")
            elif r.status == "error":
                err = _esc("[ERROR]".center(cw))
                lines.append(f"[{ERR}]{_esc(mk)}{nm}[/{ERR}]{sep}[{ERR}]{err}[/{ERR}]")
            else:
                bar = mini_bar(0.0, bw)
                lines.append(f"[{BRIGHT}]{_esc(mk)}{nm}[/{BRIGHT}]{sep}{bar}")
        return "\n".join(lines)

    # ---- initial mode ------------------------------------------------

    def _r_initial(self) -> str:
        if not self._rows:
            return f"  [{DIM}](cap fitxer detectat)[/{DIM}]"
        lines: list[str] = []
        for i, r in enumerate(self._rows):
            mk = "▸ " if i == self._sel else "  "
            tag = {"done": "✓", "error": "✗"}.get(r.status, "○")
            col = {"done": BAR_OK, "error": ERR}.get(r.status, BRIGHT)
            mc = BRIGHT if i == self._sel else DIM
            txt = _esc(f"{tag}  {r.name}  [{r.category}]")
            lines.append(f"[{mc}]{_esc(mk)}[/{mc}][{col}]{txt}[/{col}]")
        return "\n".join(lines)


# ── SegmentedBar ─────────────────────────────────────────────────────


class SegmentedBar(Static):
    """Three-segment phase progress indicator with dynamic bar width."""

    _LABELS = ("IMPORTAR", "CONVERTIR", "ENVIAR")
    # fixed overhead per segment: count ≈ 6ch, label ≈ 9ch max
    # separators: 2 × 3 = 6ch
    _OVERHEAD = sum(len(l) for l in _LABELS) + 3 * 6 + 2 * 3  # ≈ 47

    def __init__(self, **kw):
        super().__init__("", markup=True, **kw)
        self._cur = [0, 0, 0]
        self._tot = [0, 0, 0]
        self._active = [False, False, False]
        self._done = [False, False, False]
        self.update(self._build())

    @property
    def _bw(self) -> int:
        """Bar character width per segment."""
        w = self.size.width if self.size.width > 0 else 80
        return max(4, (w - self._OVERHEAD) // 3)

    def on_resize(self, event) -> None:
        self.update(self._build())

    def set_seg(self, idx: int, *, cur: int | None = None, tot: int | None = None,
                active: bool | None = None, done: bool | None = None):
        if cur is not None:
            self._cur[idx] = cur
        if tot is not None:
            self._tot[idx] = tot
        if active is not None:
            self._active[idx] = active
        if done is not None:
            self._done[idx] = done
        self.update(self._build())

    def reset(self):
        self._cur = [0, 0, 0]
        self._tot = [0, 0, 0]
        self._active = [False, False, False]
        self._done = [False, False, False]
        self.update(self._build())

    def _build(self) -> str:
        bw = self._bw
        parts: list[str] = []
        for i in range(3):
            if i:
                parts.append(f"[{DIM}] │ [/{DIM}]")
            cur, tot = self._cur[i], self._tot[i]
            if tot > 0:
                fill = max(0, min(bw, int(bw * cur / tot)))
            else:
                fill = bw if self._done[i] else 0
            bc = BAR_OK if self._active[i] else (BRIGHT if self._done[i] else DIM)
            if fill:
                parts.append(f"[{bc}]{'█' * fill}[/{bc}]")
            emp = bw - fill
            if emp:
                parts.append(f"[{DIM}]{'░' * emp}[/{DIM}]")
            cnt = f" {cur}/{tot} " if tot else "  —  "
            tc = BRIGHT if self._active[i] else DIM
            parts.append(f"[{tc}]{cnt}[/{tc}]")
            lc = WARN if self._active[i] else (BAR_OK if self._done[i] else DIM)
            parts.append(f"[bold {lc}]{self._LABELS[i]}[/bold {lc}]")
        return "".join(parts)


# ── CountdownScreen ──────────────────────────────────────────────────


class CountdownScreen(Screen):
    """Modal popup: file summary + countdown + Continue / Stop."""

    BINDINGS = [Binding("escape", "cancel", "Aturar")]

    def __init__(self, summary: List[str], seconds: int = 10):
        super().__init__()
        self._summary = summary
        self._seconds = seconds
        self._remaining = seconds

    def compose(self) -> ComposeResult:
        with Container(id="countdown-box"):
            yield Static("\n".join(self._summary), id="cd-summary")
            yield Static(self._timer_text(), id="cd-timer")
            with Horizontal(id="cd-buttons"):
                yield Button("Continuar", id="cd-go", variant="primary")
                yield Button("Aturar", id="cd-stop", classes="error")

    def on_mount(self) -> None:
        self.set_interval(1, self._tick)

    def _timer_text(self) -> str:
        return f"\n  Començant en {self._remaining}s…\n"

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self.dismiss("continue")
        else:
            try:
                self.query_one("#cd-timer", Static).update(self._timer_text())
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cd-go":
            self.dismiss("continue")
        elif event.button.id == "cd-stop":
            self.dismiss("stop")

    def action_cancel(self) -> None:
        self.dismiss("stop")


# ── ReportScreen ─────────────────────────────────────────────────────


class ReportScreen(Screen):
    """Full-screen pipeline report in Pip-Boy style.

    Receives pre-rendered Rich-markup *content* and displays it in a
    scrollable container with **Guardar Report** / **Tancar** buttons.

    Dismiss results:
        ``"save"``  – user wants to save the report to disk
        ``"close"`` – user dismissed without saving
    """

    BINDINGS = [
        Binding("escape", "close", "Tancar"),
        Binding("s", "save", "Guardar"),
    ]

    def __init__(self, content: str):
        super().__init__()
        self._content = content

    def compose(self) -> ComposeResult:
        with Container(id="report-box"):
            with VerticalScroll(id="report-scroll"):
                yield Static(self._content, id="report-body")
            with Horizontal(id="report-buttons"):
                yield Button("Guardar Report", id="rpt-save", variant="primary")
                yield Button("Tancar", id="rpt-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rpt-save":
            self.dismiss("save")
        elif event.button.id == "rpt-close":
            self.dismiss("close")

    def action_close(self) -> None:
        self.dismiss("close")

    def action_save(self) -> None:
        self.dismiss("save")
