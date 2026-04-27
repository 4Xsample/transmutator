# Transmutator V2 – API Web

API REST exposada pel servidor web (Fase 5). Base URL: `http://<host>:1312` (port per defecte).

## Arrencar el servidor

Cal fer servir l'entorn virtual del projecte (Arch i altres distribucions no permeten `pip install` al sistema).

```bash
# Des de l'arrel del projecte
source venv/bin/activate
python -m src.web_server
```

O sense activar el venv: `./venv/bin/python -m src.web_server`

Per defecte escolta a `0.0.0.0:1312` (accés des de la xarxa local). Per canviar el port:

```bash
TRANSMUTATOR_PORT=9000 python -m src.web_server
```

## Endpoints

### GET /api/config

Retorna la configuració completa per a la Web UI.

**Resposta:** `200 OK`

```json
{
  "paths": {
    "torrent_base": "/mnt/Torrent",
    "tmp_staging": "/home/user/Videos/TMP",
    "output_base": "/home/user/Videos",
    "plex_destination": "/mnt/PlexMedia/Downloads"
  },
  "qbittorrent": {
    "url": "http://localhost:8080",
    "username": "",
    "password": "",
    "processed_category": "processat",
    "modify_torrent_category": true,
    "categories": {
      "lidarr": "lidarr",
      "tv-sonarr": "tv-sonarr",
      "radarr": "radarr"
    }
  },
  "pipeline_selection": {
    "lidarr": { "importar": true, "convertir": true, "enviar": true },
    "tv-sonarr": { "importar": true, "convertir": true, "enviar": true },
    "radarr": { "importar": true, "convertir": true, "enviar": true }
  }
}
```

### PUT /api/config

Actualitza la configuració (parcial). Només s’apliquen les claus enviades.

**Cos:** `application/json`

```json
{
  "paths": {
    "torrent_base": "/mnt/Torrent",
    "tmp_staging": "~/Videos/TMP"
  },
  "qbittorrent": {
    "url": "http://localhost:8080",
    "username": "admin",
    "password": "secret",
    "processed_category": "processat"
  },
  "pipeline_selection": {
    "radarr": { "importar": true, "convertir": true, "enviar": false }
  }
}
```

**Resposta:** `200 OK` → `{ "status": "ok" }`

### POST /api/scan

Executa l’escaneig de fitxers (TMP + fonts torrent) i retorna la llista d’arxius detectats. El resultat es guarda i es retorna també a `GET /api/status`.

**Resposta:** `200 OK`

```json
{
  "files": [
    {
      "name": "movie.mkv",
      "category": "radarr",
      "status": "pending",
      "progress": 0.0
    }
  ],
  "count": 1
}
```

- **status:** `"pending"` = només a torrent (cal importar); `"done"` = ja a TMP.

### GET /api/status

Retorna l’estat del pipeline i la darrera llista d’arxius (del darrer `POST /api/scan`).

**Resposta:** `200 OK`

```json
{
  "pipeline": "idle",
  "phase": null,
  "files": [ ... ],
  "files_count": 0
}
```

- **pipeline:** `idle` | `running` (en una versió futura).
- **phase:** `null` | `extract` | `transform` | `load` (quan el pipeline estigui en marxa).

## Estàtics (SPA)

El servidor sirveix els fitxers estàtics del build del client des de `Pipboy-Transfer/dist/public`. Cal generar el build abans:

```bash
cd Pipboy-Transfer
npm install
npm run build
```

Després, obrir `http://<host>:8000/` al navegador per carregar la Web UI. Les rutes del client (p. ex. `/settings`) retornen `index.html` per permetre el routing del SPA.

## CORS

CORS està habilitat per a tots els orígens (`allow_origins=["*"]`) per poder servir el frontend des del servidor de desenvolupament de Vite (port 5000) cridant l’API al port 8000.

---
*Última actualització: Febrer 2026.*
