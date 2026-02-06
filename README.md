# Transmutator V2 ☢️

**Repositori:** [github.com/4Xsample/transmutator](https://github.com/4Xsample/transmutator)

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

### ⚠️ Pendents (Fase 2+)
- **Pausa**: Botó implementat però funcionalitat no completada (Fase 2).
- **Stop**: Atura després de l'arxiu actual; aturada immediata (kill subprocess) pendent (Fase 2).
- **Fase Extract/Load**: Només està implementada la fase Transform (conversió). Les fases Extract (còpia a TMP) i Load (enviament a Plex) queden per implementar.

### 📅 Properes Fases
Veure `docs/roadmap.md` per al roadmap complet.

## 📝 Llicència
Aquest projecte està creat per a ús personal.
