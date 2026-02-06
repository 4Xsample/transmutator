"""
Transmutator V2 - TUI application (Textual).

Pip-Boy / 4Xsample Industries style.
"""

from pathlib import Path
from typing import List

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Static, Button, ProgressBar, ListView, ListItem, Label
from textual.binding import Binding

from .file_detector import FileDetector
from .file_detector import MediaFile
from .converter import MediaConverter


# Ruta al CSS del tema (al costat d'aquest mòdul)
_CSS_PATH = Path(__file__).parent / "tui_theme.css"


class TransmutatorApp(App):
    """Aplicació principal amb estètica Pip-Boy."""

    CSS_PATH = _CSS_PATH

    TITLE = "Transmutator V2"
    SUB_TITLE = "4Xsample Industries (tm)"

    BINDINGS = [
        Binding("q", "quit", "Tancar"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_files: List[MediaFile] = []
        self.done_count = 0
        self._pipeline_running = False
        self._stop_pipeline = False

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE
        self._refresh_scan()

    def _refresh_scan(self) -> None:
        """Escaneja TMP i actualitza llista + línia d'estat."""
        by_category = FileDetector.scan_all_categories()
        self.media_files = []
        for files in by_category.values():
            self.media_files.extend(files)
        self.done_count = 0
        self._update_status_line()
        self._update_file_list()

    def _update_status_line(self) -> None:
        total = len(self.media_files)
        pending = total - self.done_count
        phase = "Importar" if total and self.done_count == 0 else ("Convertir" if pending else "Enviar")
        if total == 0:
            phase = "—"
        if self._pipeline_running:
            phase = "Convertir"
        try:
            status = self.query_one("#status-line", Static)
            status.update(
                f"Fase: {phase}  |  Total: {total}  |  Fets: {self.done_count}  |  Pendents: {pending}"
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

    def _pipeline_work(self) -> None:
        """Worker: recorre els fitxers i converteix (s'executa en un fil)."""
        app = self
        files = list(app.media_files)
        if not files:
            app.call_from_thread(lambda: app.notify("Cap fitxer a processar.", severity="warning"))
            app.call_from_thread(self._pipeline_finished)
            return
        for i, m in enumerate(files):
            if getattr(app, "_stop_pipeline", False):
                app.call_from_thread(lambda: app.notify("Pipeline aturat.", severity="information"))
                break
            app.call_from_thread(app._set_current_file, i)
            app.call_from_thread(app._on_progress, 0.0, "")

            def progress_cb(percent: float, eta: str) -> None:
                app.call_from_thread(app._on_progress, percent, eta)

            result = MediaConverter.convert(m, progress_callback=progress_cb)
            app.call_from_thread(app._on_file_done, i, result.success, result.error or "")
        app.call_from_thread(self._pipeline_finished)

    def _pipeline_finished(self) -> None:
        self._pipeline_running = False
        self._stop_pipeline = False
        self._update_status_line()
        try:
            label = self.query_one("#progress-label", Static)
            label.update("  Progrés arxiu actual: —")
        except Exception:
            pass
        self.notify("Pipeline finalitzat.", severity="information")

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            if not self._pipeline_running:
                self._refresh_scan()
            else:
                self.notify("Espera que acabi el pipeline.", severity="warning")
        elif event.button.id == "btn-start":
            if self._pipeline_running:
                self.notify("El pipeline ja s’està executant.", severity="warning")
                return
            if not self.media_files:
                self.notify("Cap fitxer a processar. Fes «Actualitzar llista» o afegeix fitxers a TMP.", severity="warning")
                return
            self._pipeline_running = True
            self._stop_pipeline = False
            self.run_worker(self._pipeline_work, thread=True)
        elif event.button.id == "btn-stop":
            if self._pipeline_running:
                self._stop_pipeline = True
                self.notify("Aturant després de l’arxiu actual…", severity="information")
            else:
                self.notify("No hi ha cap pipeline en execució.", severity="information")
        elif event.button.id == "btn-pause":
            self.notify("Pausa no implementada encara (Fase 2).", severity="information")

    def action_quit(self) -> None:
        self.exit()


def run_app() -> None:
    """Punt d'entrada per llançar la TUI."""
    app = TransmutatorApp()
    app.run()


if __name__ == "__main__":
    run_app()
