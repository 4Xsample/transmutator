| | | | | |
|:-------------:|:-------------:|:-------------:|:-------------:|:-------------:|
| ![Hack the planet](https://img.shields.io/badge/Hack-The%20Planet-orange) | [![Discord](https://img.shields.io/discord/667340023829626920?logo=discord)](https://discord.gg/ahVq54p) | [![@4Xsample@mastodon.social](https://img.shields.io/badge/Mastodon-@4Xsample-blueviolet?style=for-the-badge&logo=mastodon)](https://mastodon.social/@4Xsample) | [![4Xsample](https://img.shields.io/badge/Twitch-4Xsample-6441A4?style=for-the-badge&logo=twitch)](https://twitch.tv/4Xsample) | [![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=EFVMSRHVBNJP4) |

# Transmutator V2 ☢️

Transmutator és un pipeline ETL (Extract, Transform, Load) dissenyat per a la gestió automatitzada de llibreries de mèdia en entorns Arch Linux amb Plex. 

Inspirat en l'estètica **Pip-Boy de Fallout 4**, aquesta eina normalitza contingut de vídeo i àudio provinent de la suite ARR (Sonarr, Radarr, Lidarr) garantint la màxima compatibilitat amb clients lleugers (Apple TV HD) i protegint el seeding de torrents.

## 🚀 Característiques
- **TUI Pip-Boy Style:** Interfície retro-futurista de terminal.
- **Normalització Intelig·ligent:**
  - Vídeo: Downscale a 1080p i prioritat a *Fast Decoding*.
  - Àudio: Conversió de Lossless a MP3 320kbps i còpia directa de Lossy.
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
- `tests/`: Proves unitàries.

## 🏃 Instal·lació i Ús

### Requisits Previs
- Python 3.8+
- HandBrakeCLI instal·lat i accessible al PATH
- FFmpeg instal·lat i accessible al PATH
- qBittorrent amb WebUI activat (opcional, per auto-tagging)

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

Per provar la detecció de fitxers:

```bash
python -m src.main test
```

Per obrir la **TUI** (interfície Pip-Boy / 4Xsample Industries):

```bash
python -m src.main --tui
```

O directament: `python -m src.app`. Tancar amb **q**.

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

### ✅ Fase 2 (v0.5) - Completada
- [x] Pipeline complet: Extract (rsync Torrent → TMP), Transform (conversió), Load (rsync → Plex)
- [x] Pausa real: SIGSTOP/SIGCONT del subprocés (HandBrake/FFmpeg/rsync)
- [x] Stop immediat: SIGKILL al grup de processos (no cal esperar l'arxiu actual)
- [x] Gestió de cues: moure arxius amunt/avall amb tecles `u`/`d`
- [x] Verificació d'espai en disc abans d'Extract i Transform
- [x] Recollida de resultats per al futur report (Fase 3)

### ⚠️ Pendents (Fase 3+)
- **Report final**: Pantalla de resum amb èxits vs errors (Fase 3).
- **Guardar report**: Exportar a `.txt` o `.md` (Fase 3).
- **Poliment estètic**: Scanlines, efectes CRT, sons (Fase 3).

### 📅 Properes Fases
Veure `docs/roadmap.md` per al roadmap complet.

## 📝 Llicència

Aquest projecte es distribueix sota una llicència MIT modificada. Consulta el fitxer `LICENSE` per a més detalls.

## Disclaimer

Aquest codi s'ofereix tal com és i no es garanteix que funcioni correctament en totes les condicions. No em faig responsable dels danys que puguin resultar de l'ús d'aquesta informació. Utilitzeu-lo sota la vostra pròpia responsabilitat. Si teniu dubtes, pregunteu.
