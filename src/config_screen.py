"""
Pantalla de configuració (popup): qBittorrent URL, usuari, contrasenya,
categoria processada, modificar categoria del torrent, i noms de categories.
"""

from __future__ import annotations

from typing import Any, Dict

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Static

from .config import (
    _CATEGORIES_ORDER,
    get_qbittorrent_config,
    save_qbittorrent_config,
)

_CATEGORY_LABELS = {"lidarr": "Música", "tv-sonarr": "Sèries", "radarr": "Pel·lícules"}


class ConfigScreen(ModalScreen[None]):
    """Popup de configuració: qBittorrent i categories. Guardar escriu a config.yaml."""

    def __init__(self) -> None:
        super().__init__()
        self._values = get_qbittorrent_config()

    def compose(self) -> ComposeResult:
        with Container(id="config-container"):
            yield Static("[ 4Xsample Industries (tm) ]  CONFIGURACIÓ", id="config-title")
            with VerticalScroll(id="config-scroll"):
                yield Static("qBittorrent", classes="config-section")
                yield Static("URL", classes="config-label")
                yield Input(
                    value=self._values.get("url", "http://localhost:8080"),
                    placeholder="http://localhost:8080",
                    id="input-url",
                )
                yield Static("Usuari", classes="config-label")
                yield Input(
                    value=self._values.get("username", ""),
                    placeholder="(buit si no cal)",
                    id="input-username",
                )
                yield Static("Contrasenya", classes="config-label")
                yield Input(
                    value=self._values.get("password", ""),
                    placeholder="(buit si no cal)",
                    id="input-password",
                    password=True,
                )
                yield Static("Categoria processada", classes="config-label")
                yield Input(
                    value=self._values.get("processed_category", "processat"),
                    placeholder="processat",
                    id="input-processed-category",
                )
                yield Checkbox(
                    "Modificar categoria del torrent en acabar",
                    value=self._values.get("modify_torrent_category", True),
                    id="cb-modify-category",
                )
                yield Static("Categories (nom a qBittorrent)", classes="config-section")
                for cat in _CATEGORIES_ORDER:
                    label = _CATEGORY_LABELS.get(cat, cat)
                    yield Static(f"  {label} ({cat})", classes="config-label")
                    yield Input(
                        value=(self._values.get("categories") or {}).get(cat, cat),
                        placeholder=cat,
                        id=f"input-cat-{cat}",
                    )
            with Horizontal(id="config-buttons"):
                yield Button("Cancel·lar", id="btn-config-cancel", classes="btn-config-cancel")
                yield Button("Guardar", id="btn-config-save", variant="primary", classes="btn-config-save")

    def _get_values_from_dom(self) -> Dict[str, Any]:
        """Llegeix els camps i retorna el dict per save_qbittorrent_config."""
        out = {
            "url": "http://localhost:8080",
            "username": "",
            "password": "",
            "processed_category": "processat",
            "modify_torrent_category": True,
            "categories": {},
        }
        try:
            out["url"] = self.query_one("#input-url", Input).value or out["url"]
        except Exception:
            pass
        try:
            out["username"] = self.query_one("#input-username", Input).value or ""
        except Exception:
            pass
        try:
            out["password"] = self.query_one("#input-password", Input).value or ""
        except Exception:
            pass
        try:
            out["processed_category"] = (
                self.query_one("#input-processed-category", Input).value or "processat"
            )
        except Exception:
            pass
        try:
            out["modify_torrent_category"] = self.query_one(
                "#cb-modify-category", Checkbox
            ).value
        except Exception:
            pass
        for cat in _CATEGORIES_ORDER:
            try:
                inp = self.query_one(f"#input-cat-{cat}", Input)
                out["categories"][cat] = inp.value.strip() or cat
            except Exception:
                out["categories"][cat] = cat
        return out

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-config-cancel":
            self.dismiss()
        elif event.button.id == "btn-config-save":
            values = self._get_values_from_dom()
            save_qbittorrent_config(values)
            self.notify("Configuració guardada.", severity="information")
            self.dismiss()
