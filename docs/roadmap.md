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

## Fase 2: Control, Robustesa i Experiència Visual (v0.5 - v0.7) ✅ COMPLETADA
*   [x] Gestió de cues: Moure arxius amunt/avall (tecles `u`/`d`).
*   [x] Implementació completa del botó de Pausa (SIGSTOP/SIGCONT via ProcessHandle).
*   [x] Stop immediat: Kill subprocess (SIGKILL al grup de processos).
*   [x] Sistema de logs detallat per al report final (recollida de resultats per fase).
*   [x] Verificació d'espai en disc abans d'iniciar la fase d'importació i conversió.
*   [x] Implementació de les fases Extract (rsync Torrent → TMP) i Load (rsync → Plex).
*   [x] Llista dual amb gradient per-lletra: visualització del progrés de transferència caràcter a caràcter.
*   [x] Barra segmentada 3 fases (IMPORTAR / CONVERTIR / ENVIAR) amb comptadors en temps real.
*   [x] Barres de progrés per-arxiu integrades a la llista durant la fase Transform.
*   [x] Animació hacker entre fases: terminal scrolling amb dades tècniques reals + cites de cinema.
*   [x] Popup countdown modal amb resum de fitxers i compte enrere abans de cada fase.
*   [x] Amplada dinàmica de columnes: adaptació automàtica a la mida del terminal.
*   [x] Parsing de percentatge rsync en temps real per alimentar el gradient i la barra segmentada.

## Fase 3: Report i Poliment (v0.8 - v0.9)
*   [ ] Pantalla final de Report: Quadre d'èxits (info curiosa) vs Quadre d'errors.
*   [ ] Funció de guardat del report en fitxer `.txt` o `.md`.
*   [ ] Efectes estètics CRT: scanlines, phosphor glow, sons (si s'escau).

## Fase 4: Versió Final (v1.0)
*   [ ] Refactorització de codi i neteja de deute tècnic.
*   [ ] Creació del menú de configuració interactiu (per no haver d'editar fitxers a mà).
*   [ ] Documentació final de l'usuari.

---
*Última actualització: 06/02/2026.*  
*Estat actual: Fase 2 completada — Pipeline complet (Extract/Transform/Load), control de processos, TUI amb gradient per-lletra, animacions entre fases i amplada dinàmica.*
