| | | | | |
|:-------------:|:-------------:|:-------------:|:-------------:|:-------------:|
| ![Hack the planet](https://img.shields.io/badge/Hack-The%20Planet-orange) | [![Discord](https://img.shields.io/discord/667340023829626920?logo=discord)](https://discord.gg/ahVq54p) | [![@4Xsample@mastodon.social](https://img.shields.io/badge/Mastodon-@4Xsample-blueviolet?style=for-the-badge&logo=mastodon)](https://mastodon.social/@4Xsample) | [![4Xsample](https://img.shields.io/badge/Twitch-4Xsample-6441A4?style=for-the-badge&logo=twitch)](https://twitch.tv/4Xsample) | [![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=EFVMSRHVBNJP4) |

# Transmutator V2 ☢️

Transmutator és un pipeline ETL (Extract, Transform, Load) dissenyat per a la gestió automatitzada de llibreries de mèdia en entorns Arch Linux amb Plex. 

Inspirat en l'estètica **Pip-Boy de Fallout 4**, aquesta eina normalitza contingut de vídeo i àudio provinent de la suite ARR (Sonarr, Radarr, Lidarr) garantint la màxima compatibilitat amb clients lleugers (Apple TV HD) i protegint el seeding de torrents.

## 🚀 Característiques
- **Web UI (prioritària):** Interfície web Pip-Boy (React) servida des de Python; accés local i des de la xarxa; opcional launcher en finestra (WebView). Veure [docs/web_ui_architecture.md](docs/web_ui_architecture.md) i [docs/roadmap.md](docs/roadmap.md).
- **TUI Pip-Boy Style (secundària):** Interfície de terminal retro-futurista amb gradient per-lletra, animacions hacker i barra de progrés segmentada; mantinguda, no deprecada.
- **Pipeline complet ETL:** Extract (rsync des de torrents), Transform (HandBrake/FFmpeg), Load (rsync a Plex).
- **Normalització Intel·ligent:**
  - Vídeo: Downscale a 1080p i prioritat a *Fast Decoding*.
  - Àudio: Conversió de Lossless a MP3 320kbps i còpia directa de Lossy.
- **Control en temps real:** Pausa (SIGSTOP), reprèn (SIGCONT), stop immediat (SIGKILL).
- **Integració qBittorrent:** Auto-tagging a categoria "processat" post-processament.
- **Arquitectura Segura:** Processament en directori local (Staging) per protegir unitats de xarxa.

## 🛠️ Stack Tècnic
- Python 3
- [Textual](https://textual.textualize.io/) (TUI Framework)
- HandBrakeCLI & FFmpeg
- qbittorrent-api

## 📂 Estructura del Projecte
- `docs/`: Documentació d'arquitectura i visió.
- `src/`: Codi font de l'aplicació.
  - `app.py`: TUI principal (Textual).
  - `widgets.py`: Widgets customs (DualColumnList, SegmentedBar, CountdownScreen, ReportScreen).
  - `hacker.py`: Animació terminal entre fases.
  - `pipeline.py`: Fases Extract i Load (rsync/shutil).
  - `converter.py`: Conversió de mèdia (HandBrake/FFmpeg) + ProcessHandle.
  - `file_detector.py`: Detecció i classificació de fitxers.
  - `report.py`: Generació de reports (TUI + Markdown).
  - `config.py`: Configuració YAML.
- `tests/`: Proves unitàries (111 tests).
- `Pipboy-Transfer/`: Interfície web (React/TypeScript) amb estètica Pip-Boy: selecció de categories (Import/Convert/Send), pàgina de procés i report. Veure `Pipboy-Transfer/README.md` per executar-la.

## 🏃 Instal·lació i Ús

### Requisits Previs
- Python 3.8+
- HandBrakeCLI instal·lat i accessible al PATH
- FFmpeg instal·lat i accessible al PATH
- qBittorrent amb WebUI activat (opcional, per auto-tagging)

### Nota per Arch Linux

En Arch, `python` i moltes llibreries canvien ràpid. Per evitar errors estranys:

- usa sempre el `venv` del projecte
- no confiïs en el Python global del sistema per arrencar Transmutator
- si alguna cosa “abans funcionava” i ara no, prova primer:

```bash
./venv/bin/python -m src.main doctor
```

Aquest comandament comprova l'executable Python real, mòduls clau, eines externes i si el frontend web està buildat.

### Instal·lació

1. **Clonar el repositori:**
   ```bash
   git clone https://github.com/4Xsample/transmutator.git
   cd transmutator
   ```

2. **Crear i activar l'entorn virtual:**
   ```bash
   ./setup_venv.sh
   source venv/bin/activate
   ```

   O manualment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configurar les rutes:**
   Copia `config.example.yaml` a `config.yaml` i ajusta les rutes segons el teu sistema:
   ```bash
   cp config.example.yaml config.yaml
   # Edita config.yaml amb el teu editor preferit
   ```
   
   Principals configuracions:
   - `paths.torrent_base`: Directori base dels torrents
   - `paths.tmp_staging`: Directori temporal per staging (pots usar `~` per home)
   - `paths.plex_destination`: Destí final per Plex
   - `qbittorrent.url`: URL del WebUI de qBittorrent
   
   Si no crees `config.yaml`, s'usaran els valors per defecte (compatibles amb l'arquitectura original).

### Validació de la Configuració

Executa el script de validació per verificar que tot està configurat correctament:

```bash
python -m src.main
```

Per executar un diagnòstic més complet de l'entorn:

```bash
python -m src.main doctor
```

Per provar la detecció de fitxers:

```bash
python -m src.main test
```

Per obrir la **TUI** (interfície Pip-Boy / 4Xsample Industries):

```bash
python -m src.main --tui
```

O directament: `python -m src.app`. Tancar amb **q**.

### Web UI (Fase 5)

1. **Construir el frontend** (una vegada):
   ```bash
   cd Pipboy-Transfer && npm install && npm run build && cd ..
   ```

2. **Arrencar el servidor** (API + estàtics). Cal fer servir el **venv** (sense activar-lo no trobarà FastAPI):
   ```bash
   source venv/bin/activate
   python -m src.web_server
   ```
   O sense activar el venv (Python del venv directament):
   ```bash
   ./venv/bin/python -m src.web_server
   ```
   O amb l'entrada segura del projecte:
   ```bash
   ./run_web.sh
   ```
   Obre el navegador a `http://localhost:1312`. Des d’un altre dispositiu a la xarxa: `http://<IP-del-PC>:1312`.

   Port configurable: `TRANSMUTATOR_PORT=9000 ./venv/bin/python -m src.web_server`

3. **API:** Veure [docs/api.md](docs/api.md) per als endpoints i el contracte.

## 📋 Estat del Projecte

### ✅ Fase 0 (v0.1) - Completada
- [x] Estructura del projecte i dependències
- [x] Mòdul de configuració (hardcoded)
- [x] Detecció i classificació de fitxers
- [x] Lògica de conversió (HandBrake/FFmpeg)
- [x] Integració qBittorrent API

### ✅ Fase 1 (v0.2-0.4) - Completada
- [x] TUI bàsica amb Textual (estil Pip-Boy / 4Xsample Industries)
- [x] Visualització de progrés en temps real (barra + arxiu actual + ETA)
- [x] Llista de fitxers enllaçada a detecció i pipeline (Iniciar / Stop)
- [x] Configuració YAML (`config.yaml`) amb valors per defecte
- [x] Parser de progrés HandBrake robust (JSON `--json` + fallback text, threading)
- [x] Parser de progrés FFmpeg real (duració via `ffprobe` + `time=` de stderr)

### ✅ Fase 2 (v0.5-0.7) - Completada
- [x] Pipeline complet: Extract (rsync Torrent → TMP), Transform (conversió), Load (rsync → Plex)
- [x] Pausa real: SIGSTOP/SIGCONT del subprocés (HandBrake/FFmpeg/rsync)
- [x] Stop immediat: SIGKILL al grup de processos
- [x] Gestió de cues: moure arxius amunt/avall amb tecles `u`/`d`
- [x] Verificació d'espai en disc abans d'Extract i Transform
- [x] Llista dual amb gradient per-lletra per visualitzar transferències
- [x] Barra segmentada 3 fases (IMPORTAR / CONVERTIR / ENVIAR)
- [x] Barres de progrés per-arxiu durant Transform
- [x] Animació hacker entre fases amb dades reals + cites de cinema
- [x] Popup countdown modal amb resum i compte enrere
- [x] Amplada dinàmica de columnes (s'adapta al terminal)

### ✅ Fase 3 (v0.8) - Completada
- [x] Pantalla final de Report: quadre d'èxits amb estadístiques vs quadre d'errors
- [x] Exportació del report a fitxer `.md` (Guardar Report)
- [x] Efectes CRT: phosphor glow (tint), marc de monitor CRT (heavy border)
- [x] Animació hacker de transició al report amb dades reals del pipeline
- [x] Progrés HandBrake en temps real (JSON multilínia 1.10+, pty, throttle 1s/1%)
- [x] Countdown amb categories alineades (Pel·lícules / Episodis / Cançons)
- [x] Report i label de progrés amb amplada dinàmica segons terminal
- [x] 111 tests (pytest)

### 📅 En curs — Web UI (Fase 5)
- **API Python** + frontend Pipboy-Transfer; accés local i remot; launcher WebView opcional.
- Detalls i properes passes: `docs/roadmap.md` i `docs/web_ui_architecture.md`.

### ⚠️ En pausa (Fase 4 — TUI)
- Refactorització, menú de configuració interactiu i documentació final (prioritat inferior).

## 📝 Llicència

Aquest projecte es distribueix sota una llicència MIT modificada. Consulta el fitxer `LICENSE` per a més detalls.

## Disclaimer

Aquest codi s'ofereix tal com és i no es garanteix que funcioni correctament en totes les condicions. No em faig responsable dels danys que puguin resultar de l'ús d'aquesta informació. Utilitzeu-lo sota la vostra pròpia responsabilitat. Si teniu dubtes, pregunteu.
