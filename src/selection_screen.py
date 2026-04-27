"""
Pantalla inicial: selecció de categories i fases (Música / Sèries / Pel·lícules × Importar / Convertir / Enviar).
La selecció es guarda al config.yaml en cada canvi. Botó Següent per anar al pipeline.
"""

from __future__ import annotations

from typing import Dict

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Static

from .config import (
    _CATEGORIES_ORDER,
    _PIPELINE_SELECTION_KEYS,
    get_pipeline_selection,
    save_pipeline_selection,
)
from .config_screen import ConfigScreen

# Etiquetes per categoria (clau config -> etiqueta) i per fase
_CATEGORY_LABELS = {
    "lidarr": "Música",
    "tv-sonarr": "Sèries",
    "radarr": "Pel·lícules",
}
_PHASE_LABELS = {
    "importar": "Importar",
    "convertir": "Convertir",
    "enviar": "Enviar",
}


class SelectionScreen(Screen):
    """Pantalla inicial amb checkboxes per categoria i fases. Persistència a config.yaml."""

    def __init__(self) -> None:
        super().__init__()
        self._selection = get_pipeline_selection()
        self._updating_from_phase = False  # evita reentrada en canvis main/sub

    def compose(self) -> ComposeResult:
        with Container(id="selection-outer"):
            with Container(id="selection-container"):
                yield Static(
                    "[ 4Xsample Industries (tm) ]  QUÈ VOLS FER?",
                    id="selection-title",
                )
                with Horizontal(id="selection-columns"):
                    for cat in _CATEGORIES_ORDER:
                        label = _CATEGORY_LABELS.get(cat, cat)
                        with Vertical(id=f"selection-col-{cat}", classes="selection-col"):
                            yield Checkbox(
                                label,
                                value=self._selection[cat]["importar"]
                                and self._selection[cat]["convertir"]
                                and self._selection[cat]["enviar"],
                                id=f"cb-{cat}__main",
                            )
                            with Container(classes="selection-sub"):
                                for phase in _PIPELINE_SELECTION_KEYS:
                                    ph_label = _PHASE_LABELS.get(phase, phase)
                                    yield Checkbox(
                                        ph_label,
                                        value=self._selection[cat][phase],
                                        id=f"cb-{cat}__{phase}",
                                    )
                with Horizontal(id="selection-buttons"):
                    with Container(id="selection-btn-left"):
                        yield Button("Configuració", id="btn-config", classes="btn-config-small")
                    with Container(id="selection-btn-center"):
                        yield Button("Començar", id="btn-next", variant="primary", classes="btn-comencar")

    def on_mount(self) -> None:
        self._sync_checkboxes_from_selection()

    def _sync_checkboxes_from_selection(self) -> None:
        """Actualitza l’estat dels checkboxes des de self._selection."""
        for cat in _CATEGORIES_ORDER:
            try:
                main = self.query_one(f"#cb-{cat}__main", Checkbox)
                main.value = (
                    self._selection[cat]["importar"]
                    and self._selection[cat]["convertir"]
                    and self._selection[cat]["enviar"]
                )
            except Exception:
                pass
            for phase in _PIPELINE_SELECTION_KEYS:
                try:
                    cb = self.query_one(f"#cb-{cat}__{phase}", Checkbox)
                    cb.value = self._selection[cat][phase]
                except Exception:
                    pass

    def _get_selection_from_dom(self) -> Dict[str, Dict[str, bool]]:
        """Llegeix l’estat actual dels checkboxes i retorna el dict de selecció."""
        out = {cat: {p: True for p in _PIPELINE_SELECTION_KEYS} for cat in _CATEGORIES_ORDER}
        for cat in _CATEGORIES_ORDER:
            for phase in _PIPELINE_SELECTION_KEYS:
                try:
                    cb = self.query_one(f"#cb-{cat}__{phase}", Checkbox)
                    out[cat][phase] = cb.value
                except Exception:
                    pass
        return out

    def _persist(self) -> None:
        sel = self._get_selection_from_dom()
        self._selection = sel
        save_pipeline_selection(sel)

    def _on_main_checkbox_changed(self, category: str, value: bool) -> None:
        if self._updating_from_phase:
            return
        # Marcar la categoria → marcar totes les sub. Desmarcar la categoria → només desmarcar el principal; les sub no es toquen.
        if value:
            for phase in _PIPELINE_SELECTION_KEYS:
                try:
                    cb = self.query_one(f"#cb-{category}__{phase}", Checkbox)
                    cb.value = True
                except Exception:
                    pass
            self._selection[category] = {p: True for p in _PIPELINE_SELECTION_KEYS}
        else:
            self._selection[category] = self._get_selection_from_dom()[category]
        save_pipeline_selection(self._selection)

    def _on_phase_checkbox_changed(self, category: str) -> None:
        sel = self._get_selection_from_dom()
        all_on = all(sel[category][p] for p in _PIPELINE_SELECTION_KEYS)
        self._updating_from_phase = True
        try:
            main = self.query_one(f"#cb-{category}__main", Checkbox)
            main.value = all_on
        except Exception:
            pass
        finally:
            self._updating_from_phase = False
        self._selection = sel
        save_pipeline_selection(self._selection)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id or ""
        if not cb_id.startswith("cb-") or "__" not in cb_id:
            return
        prefix, key = cb_id.split("__", 1)
        cat = prefix.replace("cb-", "", 1)
        if key == "main":
            self._on_main_checkbox_changed(cat, event.checkbox.value)
        else:
            self._on_phase_checkbox_changed(cat)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-next":
            self._persist()
            self.dismiss(self._get_selection_from_dom())
        elif event.button.id == "btn-config":
            self.app.push_screen(ConfigScreen())
