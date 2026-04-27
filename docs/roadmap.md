# Roadmap del Projecte Transmutator V2

Aquest full de ruta detalla el desenvolupament incremental de l'aplicació Python.

**Prioritat actual (des de febrer 2026):** La **Web UI** (API + frontend Pipboy-Transfer) és el focus principal. La **TUI** (Textual) no es depreca i segueix disponible; el desenvolupament nou es centra en la interfície web. Veure [docs/web_ui_architecture.md](web_ui_architecture.md).

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

## Fase 3: Report i Poliment (v0.8 - v0.9) ✅ COMPLETADA
*   [x] Pantalla final de Report: Quadre d'èxits (info curiosa) vs Quadre d'errors.
*   [x] Funció de guardat del report en fitxer `.md`.
*   [x] Efectes estètics CRT: phosphor glow (tint), marc CRT (heavy border).
*   [x] Progrés HandBrake en temps real: suport JSON multilínia (1.10+), pty, throttle 1s/1%.
*   [x] Countdown amb categories alineades (Pel·lícules / Episodis / Cançons).
*   [x] Report i label de progrés amb amplada dinàmica; preset HandBrake via `--preset-import-file`.

## Fase 4: Versió Final TUI (v1.0) — en pausa
*   [ ] Refactorització de codi i neteja de deute tècnic.
*   [ ] Creació del menú de configuració interactiu (per no haver d'editar fitxers a mà).
*   [ ] Documentació final de l'usuari.

*(Aquesta fase queda en segon pla mentre es desenvolupa la Web UI.)*

## Fase 5: Web UI — API, Frontend i Launcher

Objectiu: Interfície web com a principal, amb la mateixa UI (Pipboy-Transfer), servida des de Python, amb opció de launcher WebView i accés remot. Veure [web_ui_architecture.md](web_ui_architecture.md).

### 5.1 Backend API (Python)
*   [ ] Servidor HTTP (FastAPI o equivalent) que exposi: escaneig de fitxers, iniciar/aturar/pausar pipeline, estat i progrés en temps real, lectura/escriptura de config.
*   [ ] Servir els fitxers estàtics del build del frontend (SPA) des del mateix servidor.
*   [ ] Enllaç a `0.0.0.0` per permetre accés des de la xarxa local (mòbil, tablet, altre PC).

### 5.2 Frontend — Connexió i manques
*   [ ] Config qBittorrent a Settings (URL, usuari, contrasenya, categoria "processat").
*   [ ] Persistència de la config (guardar/carregar des de l’API; eliminar dependència de `defaultValue` sense persistència).
*   [ ] Canvi de categoria a qBittorrent al acabar el pipeline (lògica al backend; UI només config + resum).
*   [ ] Navegació del Layout: enllaços STATS/ITEMS/DATA coherents amb les rutes reals (Home, Process, Report, Settings).
*   [ ] ProcessPage i Report amb dades reals (progrés, resultats) des de l’API en lloc de mock.

### 5.3 Launcher WebView (opcional)
*   [ ] Script/entrada (`python -m src.web_launcher` o similar) que obre la UI en una finestra PyWebView (sense barra del navegador), opcionalment arrencant el servidor si no està en marxa.

### 5.4 Documentació i poliment
*   [ ] README i docs d’usuari per arrencar el servidor web i (opcional) el launcher.
*   [ ] Notes de seguretat per accés remot (LAN; auth si es vol exposar a internet més endavant).

---

## Properes passes (ordre recomanat)

1. **Crear el mòdul del servidor web** dins de `src/`: FastAPI (o Flask) amb una ruta d’API mínima (p. ex. `GET /api/scan`, `GET /api/status`) i servir una carpeta `Pipboy-Transfer/dist` (o equivalent) com a estàtics. Un sol comandament per arrencar (p. ex. `python -m src.web_server`).
2. **Definir contracte d’API** (endpoints i payloads) i documentar-lo (OpenAPI o README) per al frontend.
3. **Al frontend:** Configurar la base URL de l’API (variable d’entorn o config de build) i connectar la pàgina Home/Settings a l’API (lectura de config, guardar config).
4. **Afegir a Settings** els camps de qBittorrent (URL, usuari, contrasenya, categoria) i persistir-los via API.
5. **Connectar ProcessPage** a l’API (iniciar pipeline, polling o WebSocket de progrés, resultats).
6. **Implementar al backend** el canvi de categoria qBittorrent al finalitzar el pipeline (reutilitzant la lògica existent) i reflectir-ho a la UI (config + report).
7. **Ajustar navegació** del Layout i Report amb dades reals.
8. **Opcional:** Launcher WebView i instruccions d’accés remot (`0.0.0.0`).

---
*Última actualització: Febrer 2026.*  
*Estat actual: Fase 3 completada (v0.8). Prioritat: Web UI (Fase 5). TUI mantinguda, no deprecada.*
