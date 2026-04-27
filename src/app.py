"""
Transmutator V2 – TUI application (Textual).

Pip-Boy / 4Xsample Industries style.
Full pipeline: Extract → (animation) → Transform → (animation) → Load.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Tuple
import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Static, Button, RichLog

from .config import Config, get_pipeline_selection
from .converter import ConversionResult, MediaConverter, ProcessHandle
from .file_detector import FileDetector, MediaFile, MediaType
from .hacker import generate_animation
from .pipeline import ExtractPhase, LoadPhase, check_disk_space, format_size
from .report import ReportData, build_report_tui, save_report, fmt_duration
from .selection_screen import SelectionScreen
from .widgets import (
    BRIGHT,
    DIM,
    WARN,
    CountdownScreen,
    DualColumnList,
    FileRow,
    ReportScreen,
    SegmentedBar,
)

_CSS_PATH = Path(__file__).parent / "tui_theme.css"


class TransmutatorApp(App):
    """Main Pip-Boy TUI application."""

    CSS_PATH = _CSS_PATH
    TITLE = "Transmutator V2"
    SUB_TITLE = "4Xsample Industries (tm)"

    BINDINGS = [
        Binding("q", "quit", "Tancar"),
        Binding("u", "move_up", "Pujar ↑"),
        Binding("d", "move_down", "Baixar ↓"),
    ]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.media_files: List[MediaFile] = []
        self._file_rows: List[FileRow] = []
        self._pipeline_running = False
        self._stop_pipeline = False
        self._paused = False
        self._ph = ProcessHandle()
        self._results: List[Tuple[MediaFile, ConversionResult]] = []
        self._sel = 0
        self._pipeline_selection = None  # Set when SelectionScreen dismisses
        # phase counters
        self._ext_done = 0
        self._ext_total = 0
        self._conv_done = 0
        self._conv_total = 0
        self._load_done = 0
        self._load_total = 0

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="main-container"):
            yield Static(
                "[ 4Xsample Industries (tm) ]  TRANSMUTATOR PIPELINE",
                id="branding",
            )
            yield SegmentedBar(id="seg-bar")
            with Container(id="list-area"):
                with VerticalScroll(id="list-scroll"):
                    yield DualColumnList(id="flist")
                yield RichLog(id="anim-log", highlight=False, markup=True)
            yield Static("  Progrés arxiu actual: —", id="progress-label")
            with Horizontal(id="button-row"):
                yield Button("Iniciar", id="btn-start", variant="primary")
                yield Button("Actualitzar", id="btn-refresh")
                yield Button("Pausa", id="btn-pause")
                yield Button("Stop", id="btn-stop", classes="error")
        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE
        self.push_screen(SelectionScreen(), self._on_selection_done)

    def _on_selection_done(self, selection) -> None:
        """Called when SelectionScreen dismisses (Següent)."""
        self._pipeline_selection = (
            selection if selection is not None else get_pipeline_selection()
        )
        self._initial_scan()

    # ── Scan helpers ──────────────────────────────────────────────────

    def _initial_scan(self) -> None:
        """Populate the file list from torrent + TMP sources."""
        rows: List[FileRow] = []
        tmp_keys: set = set()

        # Scan TMP (fast, local)
        tmp_by_cat = FileDetector.scan_all_categories()
        self.media_files = []
        for cat, files in tmp_by_cat.items():
            for f in files:
                self.media_files.append(f)
                try:
                    rel = str(f.path.relative_to(Config.get_tmp_path(cat)))
                except ValueError:
                    rel = f.path.name
                tmp_keys.add((cat, rel))

        # Scan torrent sources (may be slow / unavailable)
        if Config.TORRENT_BASE.exists():
            try:
                tor_by_cat = FileDetector.scan_torrent_sources()
            except Exception:
                tor_by_cat = {}

            for cat, files in tor_by_cat.items():
                for f in files:
                    try:
                        rel = str(f.path.relative_to(Config.get_torrent_path(cat)))
                    except ValueError:
                        rel = f.path.name
                    already = (cat, rel) in tmp_keys
                    rows.append(
                        FileRow(
                            name=f.path.name,
                            category=cat,
                            progress=100.0 if already else 0.0,
                            status="done" if already else "pending",
                        )
                    )

            # TMP-only files (placed manually)
            for cat, files in tmp_by_cat.items():
                for f in files:
                    try:
                        rel = str(f.path.relative_to(Config.get_tmp_path(cat)))
                    except ValueError:
                        rel = f.path.name
                    if (cat, rel) not in {(r.category, r.name) for r in rows}:
                        # Don't duplicate if already listed from torrent scan
                        pass  # they'd be matched by name, skip for clarity

        if not rows:
            # Fallback: just show TMP files
            for f in self.media_files:
                rows.append(
                    FileRow(
                        name=f.path.name,
                        category=f.category,
                        progress=100.0,
                        status="done",
                    )
                )

        self._file_rows = rows
        fl = self.query_one("#flist", DualColumnList)
        if Config.TORRENT_BASE.exists() and any(r.status == "pending" for r in rows):
            fl.set_mode("transfer", "TORRENT", "LOCAL")
        else:
            fl.set_mode("initial")
        fl.set_rows(self._file_rows)
        self._sel = 0
        fl.set_selected(0)

    # ── UI updaters (main thread) ─────────────────────────────────────

    def _seg(self) -> SegmentedBar:
        return self.query_one("#seg-bar", SegmentedBar)

    def _fl(self) -> DualColumnList:
        return self.query_one("#flist", DualColumnList)

    def _set_label(self, txt: str):
        try:
            self.query_one("#progress-label", Static).update(txt)
        except Exception:
            pass

    # Minimum chars reserved for suffix so "mida | % | ETA" always visible
    _SUFFIX_RESERVE = 42  # e.g. "  |  1.2 GB  |  100.0%  |  ETA: 00h00m00s"

    def _progress_text(self, name: str, suffix: str = "", prefix: str = "  ") -> str:
        """Build a progress label, truncating *name* so *suffix* stays visible."""
        try:
            w = self.size.width
        except Exception:
            w = 80
        if w <= 0:
            w = 80
        usable = max(20, w - 8)
        suffix_len = max(len(suffix), self._SUFFIX_RESERVE)
        avail = usable - len(prefix) - suffix_len
        if avail < 4:
            avail = 4
        if len(name) > avail:
            name = name[: avail - 2] + ".."
        return f"{prefix}{name}{suffix}"

    def _show_list(self):
        self.query_one("#list-scroll").display = True
        self.query_one("#anim-log").display = False

    def _show_anim(self):
        self.query_one("#list-scroll").display = False
        log = self.query_one("#anim-log", RichLog)
        log.display = True
        log.clear()

    # ── Transfer progress handler (called via call_from_thread) ───────

    def _on_transfer(self, category: str, filename: str, pct: float, phase: str):
        """Update DualColumnList row for a transfer event."""
        basename = Path(filename).name
        fl = self._fl()
        for i, r in enumerate(fl.rows):
            if r.category == category and r.name == basename:
                if pct >= 100:
                    fl.update_row(i, pct=100.0, status="done")
                    if phase == "extract":
                        self._ext_done += 1
                        self._seg().set_seg(0, cur=self._ext_done)
                    elif phase == "load":
                        self._load_done += 1
                        self._seg().set_seg(2, cur=self._load_done)
                elif pct > 0 and r.status != "done":
                    fl.update_row(i, pct=pct, status="active")
                break
        self._set_label(self._progress_text(basename, f"  |  {pct:.0f}%"))

    # ── Hacker animation (run from worker) ────────────────────────────

    def _run_animation(self, ctx: dict, duration: float = 9.0):
        """Display hacker terminal animation (blocking, from worker).

        *duration* controls the total animation time in seconds.  Sleep
        per line is computed dynamically; quote lines get 60 % extra.
        """
        self.call_from_thread(self._show_anim)
        lines = generate_animation(ctx)
        if not lines:
            return
        log = self.query_one("#anim-log", RichLog)
        n_quotes = sum(1 for l in lines if '"' in l and "—" in l)
        n_tech = len(lines) - n_quotes
        # Distribute time: quote lines get 1.6× the base delay
        divisor = n_tech + n_quotes * 1.6
        base = max(0.04, (duration - 0.3) / divisor) if divisor else 0.3
        for line in lines:
            if self._stop_pipeline:
                break
            is_quote = '"' in line and "—" in line
            style = f"italic {WARN}" if is_quote else BRIGHT
            self.call_from_thread(log.write, f"[{style}]{line}[/]")
            time.sleep(base * 1.6 if is_quote else base)
        time.sleep(0.3)

    # ── Countdown (run from worker, blocks until dismissed) ───────────

    def _run_countdown(self, summary_lines: List[str], seconds: int = 10) -> str:
        evt = threading.Event()
        holder = ["continue"]

        def on_dismiss(result):
            holder[0] = result
            evt.set()

        self.call_from_thread(
            lambda: self.push_screen(
                CountdownScreen(summary_lines, seconds), callback=on_dismiss
            )
        )
        evt.wait()
        return holder[0]

    # ── Pipeline worker ───────────────────────────────────────────────

    def _pipeline_work(self) -> None:
        app = self
        app._results = []
        app._ph = ProcessHandle()
        sel = app._pipeline_selection or get_pipeline_selection()
        cats_importar = [c for c in sel if sel.get(c, {}).get("importar", True)]
        cats_convertir = [c for c in sel if sel.get(c, {}).get("convertir", True)]
        cats_enviar = [c for c in sel if sel.get(c, {}).get("enviar", True)]

        # ── Phase 1: Extract ─────────────────────────────────────────
        run_extract = (
            Config.TORRENT_BASE.exists()
            and cats_importar
            and sum(
                1
                for r in app._file_rows
                if r.status == "pending" and r.category in cats_importar
            )
            > 0
        )
        if run_extract:
            app._ext_total = sum(
                1
                for r in app._file_rows
                if r.status == "pending" and r.category in cats_importar
            )
            app._ext_done = 0
            app.call_from_thread(
                lambda: app._seg().set_seg(0, cur=0, tot=app._ext_total, active=True)
            )
            app.call_from_thread(
                lambda: app._fl().set_mode("transfer", "TORRENT", "LOCAL")
            )

            ok, avail = check_disk_space(Config.TMP_STAGING)
            if not ok and avail:
                app.call_from_thread(
                    lambda: app.notify("Avís: < 1 GB lliure a TMP!", severity="warning")
                )

            def ext_cb(cat, fname, pct):
                app.call_from_thread(app._on_transfer, cat, fname, pct, "extract")

            if not app._stop_pipeline:
                ExtractPhase.extract_all(
                    progress_callback=ext_cb,
                    process_handle=app._ph,
                    categories=cats_importar,
                )

            app.call_from_thread(
                lambda: app._seg().set_seg(
                    0, active=False, done=True, cur=app._ext_done, tot=app._ext_total
                )
            )
        else:
            if not Config.TORRENT_BASE.exists() and cats_importar:
                app.call_from_thread(
                    lambda: app.notify(
                        "Directori torrents no accessible, saltant extracció.",
                        severity="warning",
                    )
                )
            app._ext_total = 0
            app._ext_done = 0
            app.call_from_thread(
                lambda: app._seg().set_seg(0, cur=0, tot=0, active=False, done=True)
            )

        if app._stop_pipeline:
            app.call_from_thread(app._pipeline_finished)
            return

        # Rescan TMP after extract (only if we ran extract)
        if run_extract:
            by_cat = FileDetector.scan_all_categories()
            new_files: List[MediaFile] = []
            for files in by_cat.values():
                new_files.extend(files)
            app.media_files = new_files

        # ── Transition animation → countdown ─────────────────────────
        movies = sum(1 for f in app.media_files if f.category == "radarr")
        episodes = sum(1 for f in app.media_files if f.category == "tv-sonarr")
        songs = sum(1 for f in app.media_files if f.category == "lidarr")
        vc = movies + episodes
        ac = songs
        ctx = {
            "phase": "transform",
            "files_count": len(app.media_files),
            "video_count": vc,
            "audio_count": ac,
            "video_preset": Config.VIDEO_PRESET_MOVIES,
            "audio_bitrate": Config.AUDIO_TARGET_BITRATE,
        }
        app._run_animation(ctx)

        if app._stop_pipeline:
            app.call_from_thread(app._pipeline_finished)
            return

        # Columnes alineades: etiqueta ample fix, xifres alineades a la dreta
        w = 16  # amplada etiqueta
        summary = [
            "  RESUM DE CONVERSIÓ",
            "",
            f"    {'Pel·lícules:':<{w}} {movies:>4}",
            f"    {'Episodis:':<{w}} {episodes:>4}",
            f"    {'Cançons:':<{w}} {songs:>4}",
            "    " + "─" * (w + 6),
            f"    {'TOTAL:':<{w}} {movies + episodes + songs:>4}",
        ]
        result = app._run_countdown(summary, seconds=10)
        if result == "stop":
            app._stop_pipeline = True
            app.call_from_thread(app._pipeline_finished)
            return

        # ── Phase 2: Transform ───────────────────────────────────────
        app.call_from_thread(app._show_list)
        files_to_convert = [f for f in app.media_files if f.category in cats_convertir]
        conv_rows = [
            FileRow(name=f.path.name, category=f.category, status="pending")
            for f in files_to_convert
        ]
        app._file_rows = conv_rows
        app._conv_total = len(conv_rows)
        app._conv_done = 0

        if not conv_rows:
            app.call_from_thread(
                lambda: app._seg().set_seg(1, cur=0, tot=0, active=False, done=True)
            )
            if app._stop_pipeline:
                app.call_from_thread(app._pipeline_finished)
                return
            # Skip to load phase transition
        else:
            app.call_from_thread(
                lambda: app._fl().set_mode("convert", "ARXIU", "PROGRÉS")
            )
            app.call_from_thread(lambda: app._fl().set_rows(conv_rows))
            app.call_from_thread(
                lambda: app._seg().set_seg(1, cur=0, tot=app._conv_total, active=True)
            )

            ok, avail = check_disk_space(Config.OUTPUT_BASE)
            if not ok and avail:
                app.call_from_thread(
                    lambda: app.notify(
                        "Avís: < 1 GB lliure al dir. sortida!", severity="warning"
                    )
                )

            for i, mf in enumerate(files_to_convert):
                if app._stop_pipeline:
                    app.call_from_thread(
                        lambda: app.notify("Pipeline aturat.", severity="information")
                    )
                    break
                app.call_from_thread(app._fl().update_row, i, status="active")
                app.call_from_thread(app._fl().set_selected, i)
                fsize = format_size(mf.original_size) if mf.original_size else "—"
                app.call_from_thread(
                    app._set_label,
                    app._progress_text(
                        mf.path.name,
                        f"  |  {fsize}  |  —  |  ETA: —",
                        prefix="  Progrés arxiu actual: ",
                    ),
                )

                # Throttle: actualitzar UI com a màxim cada 1 s o cada 1% per estalviar crides
                _last = [0.0, -1.0]  # [last_time, last_pct]

                def pcb(pct: float, eta: str, _i=i, _name=mf.path.name, _fsize=fsize):
                    now = time.monotonic()
                    dt = now - _last[0]
                    dp = abs(pct - _last[1])
                    if pct >= 99.9 or dt >= 1.0 or dp >= 1.0 or _last[1] < 0:
                        _last[0] = now
                        _last[1] = pct

                        def update_ui():
                            app._fl().update_row(_i, pct=pct)
                            app._fl().refresh()

                        app.call_from_thread(update_ui)
                        mida = _fsize if _fsize else "—"
                        eta_part = f"ETA: {eta}" if eta else "ETA: —"
                        suffix = f"  |  {mida}  |  {pct:.1f}%  |  {eta_part}"
                        app.call_from_thread(
                            app._set_label,
                            app._progress_text(
                                _name, suffix, prefix="  Progrés arxiu actual: "
                            ),
                        )

                res = MediaConverter.convert(
                    mf, progress_callback=pcb, process_handle=app._ph
                )
                app._results.append((mf, res))

                # Clean up source file from TMP after successful conversion
                if res.success:
                    try:
                        mf.path.unlink()  # Delete the source file from TMP
                        logger.info(f"Deleted source file after conversion: {mf.path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete source file {mf.path}: {e}")

                st = "done" if res.success else "error"
                app.call_from_thread(
                    app._fl().update_row, i, pct=100.0 if res.success else 0, status=st
                )
                if res.success:
                    app._conv_done += 1
                    app.call_from_thread(
                        lambda: app._seg().set_seg(1, cur=app._conv_done)
                    )

            app.call_from_thread(
                lambda: app._seg().set_seg(
                    1, active=False, done=True, cur=app._conv_done, tot=app._conv_total
                )
            )

        if app._stop_pipeline:
            app.call_from_thread(app._pipeline_finished)
            return

        # ── Transition animation → countdown ─────────────────────────
        load_ctx = {
            "phase": "load",
            "files_count": app._conv_done,
        }
        app._run_animation(load_ctx)

        if app._stop_pipeline:
            app.call_from_thread(app._pipeline_finished)
            return

        w2 = 20
        load_summary = [
            "  RESUM D'ENVIAMENT",
            "",
            f"    {'Fitxers convertits:':<{w2}} {app._conv_done:>4}",
            "    Destí: Plex",
        ]
        result = app._run_countdown(load_summary, seconds=10)
        if result == "stop":
            app._stop_pipeline = True
            app.call_from_thread(app._pipeline_finished)
            return

        # ── Phase 3: Load ────────────────────────────────────────────
        app.call_from_thread(app._show_list)
        load_rows = [
            FileRow(name=f.path.name, category=f.category, status="pending")
            for f, r in app._results
            if r.success and f.category in cats_enviar
        ]
        app._file_rows = load_rows
        app._load_total = len(load_rows)
        app._load_done = 0

        if load_rows and cats_enviar:
            app.call_from_thread(
                lambda: app._fl().set_mode("transfer", "LOCAL", "PLEX")
            )
            app.call_from_thread(lambda: app._fl().set_rows(load_rows))
            app.call_from_thread(
                lambda: app._seg().set_seg(2, cur=0, tot=app._load_total, active=True)
            )

            def load_cb(cat, fname, pct):
                app.call_from_thread(app._on_transfer, cat, fname, pct, "load")

            if Config.PLEX_DESTINATION.exists():
                LoadPhase.load_all(
                    progress_callback=load_cb,
                    process_handle=app._ph,
                    categories=cats_enviar,
                )
            else:
                app.call_from_thread(
                    lambda: app.notify(
                        "Directori Plex no accessible.", severity="warning"
                    )
                )

            app.call_from_thread(
                lambda: app._seg().set_seg(
                    2, active=False, done=True, cur=app._load_done, tot=app._load_total
                )
            )
        else:
            app.call_from_thread(
                lambda: app._seg().set_seg(2, cur=0, tot=0, active=False, done=True)
            )

        # ── Report animation ────────────────────────────────────────
        if app._results:
            ok = sum(1 for _, r in app._results if r.success)
            fail = sum(1 for _, r in app._results if not r.success)
            saved_bytes = sum(
                (cr.original_size or 0) - (cr.output_size or 0)
                for _, cr in app._results
                if cr.success and cr.original_size and cr.output_size
            )
            total_secs = sum(cr.duration_seconds or 0 for _, cr in app._results)
            report_ctx = {
                "phase": "report",
                "ok_count": ok,
                "fail_count": fail,
                "space_saved": format_size(max(0, saved_bytes)),
                "duration": fmt_duration(total_secs),
            }
            app._run_animation(report_ctx)

        app.call_from_thread(app._pipeline_finished)

    # ── Pipeline end ──────────────────────────────────────────────────

    def _pipeline_finished(self) -> None:
        self._pipeline_running = False
        self._stop_pipeline = False
        self._paused = False
        self._show_list()
        self._set_label("  Progrés arxiu actual: —")
        try:
            self.query_one("#btn-pause", Button).label = "Pausa"
        except Exception:
            pass

        if self._results:
            report_data = ReportData(
                results=self._results,
                extract_done=self._ext_done,
                extract_total=self._ext_total,
                load_done=self._load_done,
                load_total=self._load_total,
            )
            self._report_data = report_data
            # Usable width: terminal minus borders/padding
            rpt_w = max(40, self.size.width - 8) if self.size.width > 0 else 80
            content = build_report_tui(report_data, width=rpt_w)
            self.push_screen(ReportScreen(content), callback=self._on_report_dismiss)
        else:
            self.notify("Pipeline finalitzat.", severity="information")

    def _on_report_dismiss(self, result: str) -> None:
        """Handle ReportScreen dismissal."""
        if result == "save":
            try:
                path = save_report(self._report_data)
                self.notify(f"Report guardat: {path}", severity="information")
            except Exception as e:
                self.notify(f"Error guardant report: {e}", severity="error")

    # ── Queue management ──────────────────────────────────────────────

    def action_move_up(self) -> None:
        if self._pipeline_running or self._sel <= 0:
            return
        fl = self._fl()
        i = self._sel
        fl.rows[i], fl.rows[i - 1] = fl.rows[i - 1], fl.rows[i]
        self._sel -= 1
        fl.set_selected(self._sel)
        fl.set_rows(fl.rows)

    def action_move_down(self) -> None:
        if self._pipeline_running or self._sel >= len(self._fl().rows) - 1:
            return
        fl = self._fl()
        i = self._sel
        fl.rows[i], fl.rows[i + 1] = fl.rows[i + 1], fl.rows[i]
        self._sel += 1
        fl.set_selected(self._sel)
        fl.set_rows(fl.rows)

    # ── Button handlers ───────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "btn-refresh":
            if not self._pipeline_running:
                self._initial_scan()
            else:
                self.notify("Espera que acabi el pipeline.", severity="warning")

        elif bid == "btn-start":
            if self._pipeline_running:
                self.notify("El pipeline ja s'està executant.", severity="warning")
                return
            self._pipeline_running = True
            self._stop_pipeline = False
            self._paused = False
            self._results = []
            self._seg().reset()
            self.run_worker(self._pipeline_work, thread=True)

        elif bid == "btn-stop":
            if self._pipeline_running:
                self._stop_pipeline = True
                if self._paused:
                    self._ph.resume()
                    self._paused = False
                self._ph.kill()
                self.notify("Aturant pipeline…", severity="warning")
            else:
                self.notify("No hi ha pipeline.", severity="information")

        elif bid == "btn-pause":
            if not self._pipeline_running:
                self.notify("No hi ha pipeline.", severity="information")
                return
            if self._paused:
                self._ph.resume()
                self._paused = False
                event.button.label = "Pausa"
                self.notify("Reprès.", severity="information")
            else:
                self._ph.pause()
                self._paused = True
                event.button.label = "Reprèn"
                self.notify("Pausat.", severity="information")

    def action_quit(self) -> None:
        if self._pipeline_running:
            self._stop_pipeline = True
            self._ph.kill()
        self.exit()


def run_app() -> None:
    TransmutatorApp().run()


if __name__ == "__main__":
    run_app()
