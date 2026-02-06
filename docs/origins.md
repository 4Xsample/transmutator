# Transmutator: Anàlisi del Pipeline ETL de Mèdia (v1)

Aquest document detalla l'arquitectura, la filosofia i el funcionament tècnic dels scripts originals de gestió de mèdia (coneguts com a *Pipeline v1*).

## 1. Filosofia i Objectius
El sistema està dissenyat com un pipeline **ETL (Extract, Transform, Load)** robust, prioritzant la integritat del seeding i l'estandardització de la llibreria per sobre de la velocitat de processament.

### Objectius Clau:
1.  **Protecció del Seeding:** Els fitxers originals mai es toquen ni es modifiquen al directori de descàrrega (`/mnt/Torrent/`). Això és crític per mantenir ràtios en trackers privats.
2.  **Optimització de Xarxa:** Els directoris d'origen (Torrents) i destí (Plex) són **Unitats de Xarxa (SMB/NFS)** muntades a `/mnt/`. Per evitar saturar la xarxa fent operacions de lectura/escriptura constants (com el transcoding), el processament es fa en un directori intermedi local (`TMP`).
3.  **Estandardització de Format:** Tot el vídeo es converteix a un format predictible (Preset Handbrake) i tot l'àudio es normalitza a MP3 320kbps (màxima compatibilitat).
4.  **Atomicitat:** El contingut només arriba a la carpeta final de Plex quan està completament processat, evitant que Plex detecti fitxers corruptes o a mig convertir.

---

## 2. Arquitectura del Flux de Dades

El flux es divideix en 3 fases clares, orquestrades per l'script mestre `pipeline.sh`.

```mermaid
graph LR
    A[NAS: /mnt/Torrent] -- 1. EXTRACT (rsync) --> B[Local: ~/Videos/TMP]
    B -- 2. TRANSFORM (Handbrake/FFmpeg) --> C[Local: ~/Videos/{sonarr,radarr,Music}]
    C -- 3. LOAD (rsync) --> D[NAS: /mnt/PlexMedia]
```

---

## 3. Detall dels Processos

### Fase 1: Extracció (Staging)
**Script:** `copy_torrents_to_tmp.sh`

*   **Entrada:** `/mnt/Torrent/{tv-sonarr, radarr, lidarr}` (Xarxa)
*   **Sortida:** `/home/rossell_j/Videos/TMP/...` (Disc Local)
*   **Lògica:**
    *   Utilitza `rsync -avh --progress` per clonar l'estructura.
    *   **Per què còpia i no mou?** Per garantir que els clients de torrent (Transmission/qBittorrent) segueixin fent seeding dels fitxers originals.
    *   Crea un entorn "sandbox" (`TMP`) on podem destruir, convertir i renombrar fitxers sense risc.

### Fase 2: Transformació (Normalització)
Aquí és on el pipeline es bifurca segons el tipus de mèdia.

#### A. Vídeo (Pel·lícules i Sèries)
**Scripts:** `movies_conversion_script.sh`, `series_conversion_script.sh`

*   **Eina:** `HandBrakeCLI`
*   **Lògica:**
    1.  Escaneja `TMP` recursivament buscant extensions de vídeo (`.mkv`, `.mp4`, `.avi`, etc.).
    2.  Per cada fitxer, executa `HandBrakeCLI` usant presets personalitzats (`4Xmovie` o `4Xseries`) definits a `~/.config/ghb/presets.json`.
    3.  Desa el resultat a una carpeta de sortida intermèdia local (`~/Videos/radarr` o `~/Videos/sonarr`).
    4.  **Autoneteja:** Si (i només si) `HandBrake` retorna codi d'èxit (`0`), **esborra l'original de la carpeta TMP**. Això allibera espai automàticament a mesura que avança.

#### B. Àudio (Música)
**Script:** `audio_conversion_script.sh`

*   **Eina:** `ffmpeg` (per conversió) i `cp` (per còpia).
*   **Lògica Condicional:**
    *   **Si és Lossy (MP3):** No re-comprimeix. Fa una còpia directa (`cp`) per evitar pèrdua de qualitat generacional.
    *   **Si és Lossless/Altres (FLAC, WAV, OGG, AIFF, M4A):** Detecta format d'alta qualitat i el converteix a **MP3 320kbps** (CBR) usant `ffmpeg -ab 320k`.
        *   *Motiu:* Màxima compatibilitat amb reproductors mòbils i estalvi d'espai, mantenint qualitat perceptualment transparent.
    *   **Ignora:** Fitxers que no són àudio (caràtules, nfo, etc.).
*   **Sortida:** `~/Music/`.
*   **Autoneteja:** Igual que el vídeo, esborra l'original de `TMP` després de processar-lo correctament.

### Fase 3: Càrrega (Delivery)
**Scripts:** `move_movies_to_plex.sh`, `move_series_to_plex.sh`, `move_music_to_plex.sh`

*   **Entrada:** Carpetes locals processades (`~/Videos/radarr`, `~/Music`, etc.).
*   **Sortida:** `/mnt/PlexMedia/Downloads/...` (Xarxa).
*   **Lògica:**
    *   Utilitza `rsync -avh --remove-source-files`.
    *   Aquesta comanda mou el fitxer a la unitat de xarxa i, un cop verificada la transferència, esborra la còpia local processada.
    *   **Resultat:** El disc local queda net, preparat per al següent lot.

---

## 4. L'Orquestrador: `pipeline.sh`

Un script "wrapper" que permet executar tot el procés o parts d'ell de manera granular.

*   **Flags:** `--copia-pelis`, `--conv-audio`, `--mou-tot`, etc.
*   **Utilitat:** Permet recuperar-se d'errors (ex: si falla la xarxa al pas 3, no cal repetir els passos 1 i 2) o prioritzar recursos (ex: copiar tot ara, però convertir només àudio perquè necessito la CPU).

## 5. Resum de Rutes

| Tipus | Origen (Seeding/Xarxa) | Staging (Local) | Processat (Local) | Destí Final (Plex/Xarxa) |
| :--- | :--- | :--- | :--- | :--- |
| **Sèries** | `/mnt/Torrent/tv-sonarr` | `~/Videos/TMP/tv-sonarr` | `~/Videos/sonarr` | `/mnt/PlexMedia/Downloads/` |
| **Pelis** | `/mnt/Torrent/radarr` | `~/Videos/TMP/radarr` | `~/Videos/radarr` | `/mnt/PlexMedia/Downloads/` |
| **Música** | `/mnt/Torrent/lidarr` | `~/Videos/TMP/lidarr` | `~/Music` | `/mnt/PlexMedia/Downloads/Music/` |

---
*Document generat automàticament per Gemini CLI el 25/01/2026.*
