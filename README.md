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
   git clone <repo-url>
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
   Edita `src/config.py` per ajustar les rutes segons el teu sistema:
   - `TORRENT_BASE`: Directori base dels torrents
   - `TMP_STAGING`: Directori temporal per staging
   - `PLEX_DESTINATION`: Destí final per Plex
   - `QBITTORRENT_URL`: URL del WebUI de qBittorrent

### Validació de la Configuració

Executa el script de validació per verificar que tot està configurat correctament:

```bash
python -m src.main
```

Per provar la detecció de fitxers:

```bash
python -m src.main test
```

## 📋 Estat del Projecte

### ✅ Fase 0 (v0.1) - Completada
- [x] Estructura del projecte i dependències
- [x] Mòdul de configuració (hardcoded)
- [x] Detecció i classificació de fitxers
- [x] Lògica de conversió (HandBrake/FFmpeg)
- [x] Integració qBittorrent API

### 🚧 Fase 1 (v0.2-0.4) - En desenvolupament
- [ ] TUI bàsica amb Textual (estil Pip-Boy)
- [ ] Visualització de progrés en temps real
- [ ] Llista scrollable de fitxers

### 📅 Properes Fases
Veure `docs/roadmap.md` per al roadmap complet.

## 📝 Llicència
Aquest projecte està creat per a ús personal.
