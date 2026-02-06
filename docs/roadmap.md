# Roadmap del Projecte Transmutator V2

Aquest full de ruta detalla el desenvolupament incremental de l'aplicació Python.

## Fase 0: Preparació i Lògica Core (v0.1)
*   [ ] Creació de l'entorn virtual (`venv`) i instal·lació de dependències (`rich`, `textual`, `qbittorrent-api`).
*   [ ] Desenvolupament del mòdul de configuració (inicialment hardcoded/JSON).
*   [ ] Implementació de la lògica de detecció de fitxers i classificació (Vídeo/Àudio).
*   [ ] Re-implementació de la lògica de conversió (Handbrake/FFmpeg) en Python usant `subprocess`.
*   [ ] Implementació del mòdul qBittorrent-api per al canvi de categoria.

## Fase 1: TUI Bàsica i Progrés (v0.2 - v0.4)
*   [ ] Disseny de l'esquelet de la TUI amb `Textual` (estil Pip-Boy).
*   [ ] Pantalla de selecció d'opcions inicial.
*   [ ] Visualització de la llista de fitxers i estat global del procés.
*   [ ] Implementació del parser de `stdout` per mostrar el progrés en temps real (percentatge/ETA).

## Fase 2: Control i Robustesa (v0.5 - v0.7)
*   [ ] Gestió de cues: Moure arxius amunt/avall.
*   [ ] Implementació dels botons de Pausa i Stop (aturada controlada dels subprocessos).
*   [ ] Sistema de logs detallat per al report final.
*   [ ] Verificació d'espai en disc abans d'iniciar la fase d'importació.

## Fase 3: Report i Poliment (v0.8 - v0.9)
*   [ ] Pantalla final de Report: Quadre d'èxits (info curiosa) vs Quadre d'errors.
*   [ ] Funció de guardat del report en fitxer `.txt` o `.md`.
*   [ ] Poliment estètic "Pip-Boy": efectes visuals, scanlines, colors i sons (si s'escau).

## Fase 4: Versió Final (v1.0)
*   [ ] Refactorització de codi i neteja de deute tècnic.
*   [ ] Creació del menú de configuració interactiu (per no haver d'editar fitxers a mà).
*   [ ] Documentació final de l'usuari.

---
*Última actualització: 25/01/2026.*
