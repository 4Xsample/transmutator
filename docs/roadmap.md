# Roadmap del Projecte Transmutator V2

Aquest full de ruta detalla el desenvolupament incremental de l'aplicació Python.

## Fase 0: Preparació i Lògica Core (v0.1) ✅ COMPLETADA
*   [x] Creació de l'entorn virtual (`venv`) i instal·lació de dependències (`rich`, `textual`, `qbittorrent-api`).
*   [x] Desenvolupament del mòdul de configuració (YAML amb fallback a valors per defecte).
*   [x] Implementació de la lògica de detecció de fitxers i classificació (Vídeo/Àudio).
*   [x] Re-implementació de la lògica de conversió (Handbrake/FFmpeg) en Python usant `subprocess`.
*   [x] Implementació del mòdul qBittorrent-api per al canvi de categoria.

## Fase 1: TUI Bàsica i Progrés (v0.2 - v0.4) ✅ COMPLETADA
*   [x] Disseny de l'esquelet de la TUI amb `Textual` (estil Pip-Boy / 4Xsample Industries).
*   [x] Pantalla principal amb llista de fitxers i controls (Iniciar, Stop, Actualitzar).
*   [x] Visualització de la llista de fitxers i estat global del procés (Fase, Total, Fets, Pendents).
*   [x] Implementació del parser de `stdout` per mostrar el progrés en temps real (percentatge/ETA).
*   [x] Worker thread per executar conversions sense bloquejar la UI.
*   [x] Configuració YAML (`config.yaml`) amb suport per a totes les rutes i opcions.
*   [x] Parser de progrés HandBrake robust (JSON `--json` + fallback text, threading per evitar deadlocks).
*   [x] Parser de progrés FFmpeg real (duració via `ffprobe` + parsing `time=` de stderr).
*   [x] Visualització d'ETA al label de progrés de la TUI.

## Fase 2: Control i Robustesa (v0.5 - v0.7)
*   [ ] Gestió de cues: Moure arxius amunt/avall.
*   [ ] Implementació completa del botó de Pausa (aturada controlada dels subprocessos).
*   [ ] Stop immediat: Kill subprocess en lloc d'esperar a l'arxiu actual.
*   [ ] Sistema de logs detallat per al report final.
*   [ ] Verificació d'espai en disc abans d'iniciar la fase d'importació.
*   [ ] Implementació de les fases Extract (còpia Torrent → TMP) i Load (enviament a Plex).

## Fase 3: Report i Poliment (v0.8 - v0.9)
*   [ ] Pantalla final de Report: Quadre d'èxits (info curiosa) vs Quadre d'errors.
*   [ ] Funció de guardat del report en fitxer `.txt` o `.md`.
*   [ ] Poliment estètic "Pip-Boy": efectes visuals, scanlines, colors i sons (si s'escau).

## Fase 4: Versió Final (v1.0)
*   [ ] Refactorització de codi i neteja de deute tècnic.
*   [ ] Creació del menú de configuració interactiu (per no haver d'editar fitxers a mà).
*   [ ] Documentació final de l'usuari.

---
*Última actualització: 06/02/2026.*  
*Estat actual: Fase 1 completada - TUI funcional amb pipeline de conversió, parsers de progrés robusts i ETA en temps real.*
