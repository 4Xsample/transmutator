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

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Static, Button, RichLog

from .config import Config
from .converter import ConversionResult, MediaConverter, ProcessHandle
from .file_detector import FileDetector, MediaFile, MediaType
from .hacker import generate_animation
from .pipeline import ExtractPhase, LoadPhase, check_disk_space, format_size
from .widgets import (
    BRIGHT, DIM, WARN,
    CountdownScreen,
    DualColumnList,
    FileRow,
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
                    rows.append(FileRow(
                        name=f.path.name,
                        category=cat,
                        progress=100.0 if already else 0.0,
                        status="done" if already else "pending",
                    ))

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
                rows.append(FileRow(
                    name=f.path.name,
                    category=f.category,
                    progress=100.0,
                    status="done",
                ))

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
        self._set_label(f"  {basename}  |  {pct:.0f}%")

    # ── Hacker animation (run from worker) ────────────────────────────

    def _run_animation(self, ctx: dict):
        """Display hacker terminal animation (blocking, from worker)."""
        self.call_from_thread(self._show_anim)
        lines = generate_animation(ctx)
        log = self.query_one("#anim-log", RichLog)
        for line in lines:
            if self._stop_pipeline:
                break
            is_quote = '"' in line and "—" in line
            style = f"italic {WARN}" if is_quote else BRIGHT
            self.call_from_thread(log.write, f"[{style}]{line}[/]")
            time.sleep(0.12 if is_quote else 0.07)
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

        # ── Phase 1: Extract ─────────────────────────────────────────
        if Config.TORRENT_BASE.exists():
            app._ext_total = sum(1 for r in app._file_rows if r.status == "pending")
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
                ExtractPhase.extract_all(progress_callback=ext_cb, process_handle=app._ph)

            app.call_from_thread(
                lambda: app._seg().set_seg(0, active=False, done=True,
                                            cur=app._ext_done, tot=app._ext_total)
            )
        else:
            app.call_from_thread(
                lambda: app.notify("Directori torrents no accessible, saltant extracció.",
                                    severity="warning")
            )

        if app._stop_pipeline:
            app.call_from_thread(app._pipeline_finished)
            return

        # Rescan TMP after extract
        by_cat = FileDetector.scan_all_categories()
        new_files: List[MediaFile] = []
        for files in by_cat.values():
            new_files.extend(files)
        app.media_files = new_files

        # ── Transition animation → countdown ─────────────────────────
        vc = sum(1 for f in app.media_files if f.media_type == MediaType.VIDEO)
        ac = sum(1 for f in app.media_files if f.media_type == MediaType.AUDIO)
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

        summary = [
            f"  RESUM DE CONVERSIÓ",
            "",
            f"    Pel·lícules / Sèries:  {vc}",
            f"    Àlbums / Cançons:      {ac}",
            f"    ─────────────────────────",
            f"    TOTAL:                 {vc + ac}",
        ]
        result = app._run_countdown(summary, seconds=10)
        if result == "stop":
            app._stop_pipeline = True
            app.call_from_thread(app._pipeline_finished)
            return

        # ── Phase 2: Transform ───────────────────────────────────────
        app.call_from_thread(app._show_list)
        conv_rows = [
            FileRow(name=f.path.name, category=f.category, status="pending")
            for f in app.media_files
        ]
        app._file_rows = conv_rows
        app._conv_total = len(conv_rows)
        app._conv_done = 0

        app.call_from_thread(lambda: app._fl().set_mode("convert", "ARXIU", "PROGRÉS"))
        app.call_from_thread(lambda: app._fl().set_rows(conv_rows))
        app.call_from_thread(
            lambda: app._seg().set_seg(1, cur=0, tot=app._conv_total, active=True)
        )

        ok, avail = check_disk_space(Config.OUTPUT_BASE)
        if not ok and avail:
            app.call_from_thread(
                lambda: app.notify("Avís: < 1 GB lliure al dir. sortida!", severity="warning")
            )

        for i, mf in enumerate(app.media_files):
            if app._stop_pipeline:
                app.call_from_thread(
                    lambda: app.notify("Pipeline aturat.", severity="information")
                )
                break
            app.call_from_thread(app._fl().update_row, i, status="active")
            app.call_from_thread(app._fl().set_selected, i)
            app.call_from_thread(
                app._set_label,
                f"  Progrés arxiu actual: {mf.path.name}",
            )

            def pcb(pct: float, eta: str, _i=i, _name=mf.path.name):
                app.call_from_thread(app._fl().update_row, _i, pct=pct)
                eta_s = f"  |  ETA: {eta}" if eta else ""
                app.call_from_thread(
                    app._set_label,
                    f"  Progrés arxiu actual: {_name}  |  {pct:.1f}%{eta_s}",
                )

            res = MediaConverter.convert(mf, progress_callback=pcb, process_handle=app._ph)
            app._results.append((mf, res))

            st = "done" if res.success else "error"
            app.call_from_thread(app._fl().update_row, i, pct=100.0 if res.success else 0, status=st)
            if res.success:
                app._conv_done += 1
                app.call_from_thread(lambda: app._seg().set_seg(1, cur=app._conv_done))

        app.call_from_thread(
            lambda: app._seg().set_seg(1, active=False, done=True,
                                        cur=app._conv_done, tot=app._conv_total)
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

        load_summary = [
            "  RESUM D'ENVIAMENT",
            "",
            f"    Fitxers convertits:  {app._conv_done}",
            f"    Destí: Plex",
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
            for f, r in app._results if r.success
        ]
        app._file_rows = load_rows
        app._load_total = len(load_rows)
        app._load_done = 0

        app.call_from_thread(lambda: app._fl().set_mode("transfer", "LOCAL", "PLEX"))
        app.call_from_thread(lambda: app._fl().set_rows(load_rows))
        app.call_from_thread(
            lambda: app._seg().set_seg(2, cur=0, tot=app._load_total, active=True)
        )

        def load_cb(cat, fname, pct):
            app.call_from_thread(app._on_transfer, cat, fname, pct, "load")

        if Config.PLEX_DESTINATION.exists():
            LoadPhase.load_all(progress_callback=load_cb, process_handle=app._ph)
        else:
            app.call_from_thread(
                lambda: app.notify("Directori Plex no accessible.", severity="warning")
            )

        app.call_from_thread(
            lambda: app._seg().set_seg(2, active=False, done=True,
                                        cur=app._load_done, tot=app._load_total)
        )
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
        ok = sum(1 for _, r in self._results if r.success)
        fail = sum(1 for _, r in self._results if not r.success)
        if self._results:
            self.notify(
                f"Pipeline finalitzat. Èxits: {ok}, Errors: {fail}",
                severity="information" if fail == 0 else "warning",
            )
        else:
            self.notify("Pipeline finalitzat.", severity="information")

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
