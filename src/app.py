"""
Transmutator V2 - TUI application (Textual).

Pip-Boy / 4Xsample Industries style.
"""

from pathlib import Path
from typing import List, Tuple

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Static, Button, ProgressBar, ListView, ListItem, Label
from textual.binding import Binding

from .file_detector import FileDetector
from .file_detector import MediaFile
from .converter import MediaConverter, ConversionResult, ProcessHandle
from .pipeline import ExtractPhase, LoadPhase, check_disk_space, format_size
from .config import Config


# Ruta al CSS del tema (al costat d'aquest mòdul)
_CSS_PATH = Path(__file__).parent / "tui_theme.css"


class TransmutatorApp(App):
    """Aplicació principal amb estètica Pip-Boy."""

    CSS_PATH = _CSS_PATH

    TITLE = "Transmutator V2"
    SUB_TITLE = "4Xsample Industries (tm)"

    BINDINGS = [
        Binding("q", "quit", "Tancar"),
        Binding("u", "move_up", "Pujar ↑"),
        Binding("d", "move_down", "Baixar ↓"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_files: List[MediaFile] = []
        self.done_count = 0
        self._pipeline_running = False
        self._stop_pipeline = False
        self._paused = False
        self._process_handle = ProcessHandle()
        self._results: List[Tuple[MediaFile, ConversionResult]] = []
        self._current_phase = "—"

    # ── Lifecycle ─────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE
        self._refresh_scan()

    # ── Scan & UI helpers ─────────────────────────────────────────────

    def _refresh_scan(self) -> None:
        """Escaneja TMP i actualitza llista + línia d'estat."""
        by_category = FileDetector.scan_all_categories()
        self.media_files = []
        for files in by_category.values():
            self.media_files.extend(files)
        self.done_count = 0
        self._update_status_line()
        self._update_file_list()

    def _set_phase(self, phase: str) -> None:
        """Actualitza la fase actual del pipeline."""
        self._current_phase = phase
        self._update_status_line()

    def _set_pipeline_status(self, msg: str) -> None:
        """Mostra un missatge d'estat durant Extract/Load."""
        try:
            label = self.query_one("#progress-label", Static)
            label.update(f"  {msg}")
        except Exception:
            pass

    def _update_status_line(self) -> None:
        total = len(self.media_files)
        pending = total - self.done_count
        phase = self._current_phase
        paused = " [PAUSAT]" if self._paused else ""
        try:
            status = self.query_one("#status-line", Static)
            status.update(
                f"Fase: {phase}{paused}  |  Total: {total}"
                f"  |  Fets: {self.done_count}  |  Pendents: {pending}"
            )
        except Exception:
            pass

    def _update_file_list(self) -> None:
        try:
            list_view = self.query_one("#file-list", ListView)
            list_view.clear()
            if not self.media_files:
                list_view.append(ListItem(Label("(cap fitxer detectat)")))
            else:
                for m in self.media_files:
                    tag = "✓" if m.processed else ("…" if getattr(m, "_current", False) else "○")
                    err = "  [ERROR]" if m.error else ""
                    label = f"  {tag}  {m.path.name}  [{m.media_type.value}]{err}"
                    list_view.append(ListItem(Label(label)))
        except Exception:
            pass

    def _set_current_file(self, index: int) -> None:
        """Marca l'arxiu actual i actualitza la UI."""
        for i, m in enumerate(self.media_files):
            m._current = (i == index)  # type: ignore[attr-defined]
        self._update_status_line()
        self._update_file_list()
        try:
            label = self.query_one("#progress-label", Static)
            name = self.media_files[index].path.name if 0 <= index < len(self.media_files) else "—"
            label.update(f"  Progrés arxiu actual: {name}")
        except Exception:
            pass

    def _on_progress(self, percent: float, eta: str) -> None:
        """Actualitza la barra de progrés i l'ETA (cridat des del worker)."""
        try:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.update(progress=min(100, max(0, int(percent))))
        except Exception:
            pass
        try:
            label = self.query_one("#progress-label", Static)
            current_name = "—"
            for m in self.media_files:
                if getattr(m, "_current", False):
                    current_name = m.path.name
                    break
            eta_text = f"  |  ETA: {eta}" if eta else ""
            label.update(f"  Progrés arxiu actual: {current_name}  |  {percent:.1f}%{eta_text}")
        except Exception:
            pass

    def _on_file_done(self, index: int, success: bool, error_msg: str = "") -> None:
        """Marca l'arxiu com fet i actualitza la UI (cridat des del worker)."""
        if 0 <= index < len(self.media_files):
            m = self.media_files[index]
            m._current = False  # type: ignore[attr-defined]
            m.processed = success
            if not success:
                m.error = error_msg or "Error desconegut"
        self.done_count = sum(1 for m in self.media_files if m.processed)
        self._update_status_line()
        self._update_file_list()
        try:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.update(progress=0)
        except Exception:
            pass

    # ── Pipeline worker ───────────────────────────────────────────────

    def _pipeline_work(self) -> None:
        """Full pipeline: Extract → Transform → Load (s'executa en un fil)."""
        app = self
        app._results = []
        app._process_handle = ProcessHandle()

        # ── Phase 1: Extract (Importar) ──────────────────────────────
        if Config.TORRENT_BASE.exists():
            app.call_from_thread(app._set_phase, "Importar")
            app.call_from_thread(
                lambda: app.notify("Fase 1/3: Importar (copiant fitxers a TMP)…")
            )

            # Disk space check
            ok, avail = check_disk_space(Config.TMP_STAGING)
            if avail > 0:
                app.call_from_thread(
                    lambda a=avail: app.notify(
                        f"Espai disponible a TMP: {format_size(a)}",
                        severity="information",
                    )
                )
            if not ok and avail > 0:
                app.call_from_thread(
                    lambda: app.notify(
                        "Avís: menys d'1 GB lliure a TMP!", severity="warning"
                    )
                )

            def extract_status(msg: str) -> None:
                app.call_from_thread(app._set_pipeline_status, msg)

            if not getattr(app, "_stop_pipeline", False):
                extract_result = ExtractPhase.extract_all(
                    progress_callback=extract_status,
                    process_handle=app._process_handle,
                )
                if extract_result.files_transferred > 0:
                    app.call_from_thread(
                        lambda n=extract_result.files_transferred: app.notify(
                            f"Extracció: {n} fitxer(s) copiats.",
                            severity="information",
                        )
                    )
                if not extract_result.success and extract_result.error:
                    app.call_from_thread(
                        lambda e=extract_result.error: app.notify(
                            f"Avís extracció: {e}", severity="warning"
                        )
                    )
        else:
            app.call_from_thread(
                lambda: app.notify(
                    "Directori de torrents no accessible, saltant extracció.",
                    severity="warning",
                )
            )

        if getattr(app, "_stop_pipeline", False):
            app.call_from_thread(
                lambda: app.notify("Pipeline aturat.", severity="information")
            )
            app.call_from_thread(self._pipeline_finished)
            return

        # Rescan TMP after extract (built in worker to avoid thread sync issues)
        by_category = FileDetector.scan_all_categories()
        new_files: List[MediaFile] = []
        for files in by_category.values():
            new_files.extend(files)
        app.media_files = new_files  # atomic pointer swap
        app.done_count = 0
        app.call_from_thread(app._update_status_line)
        app.call_from_thread(app._update_file_list)

        # ── Phase 2: Transform (Convertir) ───────────────────────────
        app.call_from_thread(app._set_phase, "Convertir")
        files = list(app.media_files)

        if not files:
            app.call_from_thread(
                lambda: app.notify("Cap fitxer a processar.", severity="warning")
            )

        # Disk space check before conversion
        ok, avail = check_disk_space(Config.OUTPUT_BASE)
        if not ok and avail > 0:
            app.call_from_thread(
                lambda: app.notify(
                    "Avís: menys d'1 GB lliure al directori de sortida!",
                    severity="warning",
                )
            )

        for i, m in enumerate(files):
            if getattr(app, "_stop_pipeline", False):
                app.call_from_thread(
                    lambda: app.notify("Pipeline aturat.", severity="information")
                )
                break
            app.call_from_thread(app._set_current_file, i)
            app.call_from_thread(app._on_progress, 0.0, "")

            def progress_cb(percent: float, eta: str) -> None:
                app.call_from_thread(app._on_progress, percent, eta)

            result = MediaConverter.convert(
                m,
                progress_callback=progress_cb,
                process_handle=app._process_handle,
            )
            app._results.append((m, result))
            app.call_from_thread(
                app._on_file_done, i, result.success, result.error or ""
            )

        if getattr(app, "_stop_pipeline", False):
            app.call_from_thread(self._pipeline_finished)
            return

        # ── Phase 3: Load (Enviar) ───────────────────────────────────
        if Config.PLEX_DESTINATION.exists():
            app.call_from_thread(app._set_phase, "Enviar")
            app.call_from_thread(
                lambda: app.notify("Fase 3/3: Enviar (movent fitxers a Plex)…")
            )

            def load_status(msg: str) -> None:
                app.call_from_thread(app._set_pipeline_status, msg)

            load_result = LoadPhase.load_all(
                progress_callback=load_status,
                process_handle=app._process_handle,
            )
            if load_result.files_transferred > 0:
                app.call_from_thread(
                    lambda n=load_result.files_transferred: app.notify(
                        f"Enviament: {n} fitxer(s) moguts a Plex.",
                        severity="information",
                    )
                )
            if not load_result.success:
                app.call_from_thread(
                    lambda e=load_result.error: app.notify(
                        f"Error d'enviament: {e}", severity="error"
                    )
                )
        else:
            app.call_from_thread(
                lambda: app.notify(
                    "Directori Plex no accessible, saltant enviament.",
                    severity="warning",
                )
            )

        app.call_from_thread(self._pipeline_finished)

    def _pipeline_finished(self) -> None:
        self._pipeline_running = False
        self._stop_pipeline = False
        self._paused = False
        self._current_phase = "—"
        self._update_status_line()
        try:
            label = self.query_one("#progress-label", Static)
            label.update("  Progrés arxiu actual: —")
        except Exception:
            pass
        # Reset pause button label
        try:
            btn = self.query_one("#btn-pause", Button)
            btn.label = "Pausa"
        except Exception:
            pass
        # Summary
        successes = sum(1 for _, r in self._results if r.success)
        failures = sum(1 for _, r in self._results if not r.success)
        if self._results:
            self.notify(
                f"Pipeline finalitzat. Èxits: {successes}, Errors: {failures}",
                severity="information" if failures == 0 else "warning",
            )
        else:
            self.notify("Pipeline finalitzat.", severity="information")

    # ── Queue management ──────────────────────────────────────────────

    def action_move_up(self) -> None:
        """Mou l'arxiu seleccionat una posició amunt a la cua."""
        if self._pipeline_running:
            return
        try:
            lv = self.query_one("#file-list", ListView)
            idx = lv.index
            if idx is not None and idx > 0:
                self.media_files[idx], self.media_files[idx - 1] = (
                    self.media_files[idx - 1],
                    self.media_files[idx],
                )
                self._update_file_list()
                lv.index = idx - 1
        except Exception:
            pass

    def action_move_down(self) -> None:
        """Mou l'arxiu seleccionat una posició avall a la cua."""
        if self._pipeline_running:
            return
        try:
            lv = self.query_one("#file-list", ListView)
            idx = lv.index
            if idx is not None and idx < len(self.media_files) - 1:
                self.media_files[idx], self.media_files[idx + 1] = (
                    self.media_files[idx + 1],
                    self.media_files[idx],
                )
                self._update_file_list()
                lv.index = idx + 1
        except Exception:
            pass

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="main-container"):
            yield Static("[ 4Xsample Industries (tm) ]  TRANSMUTATOR PIPELINE", id="branding")
            yield Static("Fase: —  |  Total: 0  |  Fets: 0  |  Pendents: 0", id="status-line")
            yield Static("")
            yield ListView(
                ListItem(Label("(cap fitxer detectat)")),
                id="file-list",
            )
            yield Static("")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Static("  Progrés arxiu actual: —", id="progress-label")
            yield Static("")
            with Horizontal():
                yield Button("Iniciar", id="btn-start", variant="primary")
                yield Button("Actualitzar llista", id="btn-refresh")
                yield Button("Pausa", id="btn-pause")
                yield Button("Stop", id="btn-stop", classes="error")
        yield Footer()

    # ── Button handlers ───────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            if not self._pipeline_running:
                self._refresh_scan()
            else:
                self.notify("Espera que acabi el pipeline.", severity="warning")

        elif event.button.id == "btn-start":
            if self._pipeline_running:
                self.notify("El pipeline ja s'està executant.", severity="warning")
                return
            if not self.media_files and not Config.TORRENT_BASE.exists():
                self.notify(
                    "Cap fitxer a TMP i directori de torrents no accessible.",
                    severity="warning",
                )
                return
            self._pipeline_running = True
            self._stop_pipeline = False
            self._paused = False
            self._results = []
            self.run_worker(self._pipeline_work, thread=True)

        elif event.button.id == "btn-stop":
            if self._pipeline_running:
                self._stop_pipeline = True
                # Resume first if paused, then kill
                if self._paused:
                    self._process_handle.resume()
                    self._paused = False
                self._process_handle.kill()
                self.notify("Aturant pipeline immediatament…", severity="warning")
            else:
                self.notify("No hi ha cap pipeline en execució.", severity="information")

        elif event.button.id == "btn-pause":
            if not self._pipeline_running:
                self.notify("No hi ha cap pipeline en execució.", severity="information")
                return
            if self._paused:
                self._process_handle.resume()
                self._paused = False
                event.button.label = "Pausa"
                self.notify("Pipeline reprès.", severity="information")
            else:
                self._process_handle.pause()
                self._paused = True
                event.button.label = "Reprèn"
                self.notify("Pipeline pausat.", severity="information")
            self._update_status_line()

    def action_quit(self) -> None:
        if self._pipeline_running:
            self._stop_pipeline = True
            self._process_handle.kill()
        self.exit()


def run_app() -> None:
    """Punt d'entrada per llançar la TUI."""
    app = TransmutatorApp()
    app.run()


if __name__ == "__main__":
    run_app()
