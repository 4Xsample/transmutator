# Workflow del Projecte Transmutator

Aquest document descriu el flux de treball de l'usuari i una anàlisi tècnica del procediment.

## Descripció del Workflow (Original)

1. **Suite ARR:** Les aplicacions (Sonarr, Radarr, Lidarr) gestionen la cerca i l'encàrrec de contingut.
2. **qBittorrent:** Descarrega els fitxers incomplets a carpetes temporals i, un cop completats, els mou a la carpeta de la seva categoria (sonarr, radarr, etc.) mantenint el seeding.
3. **Execució de Scripts:** S'executa el pipeline de Transmutator (v1) per copiar, convertir (Handbrake/FFmpeg) i moure els fitxers processats.
4. **Importació Manual:** Un cop el pipeline acaba, l'usuari importa els arxius des de la suite ARR manualment per verificar que la identificació sigui correcta.
5. **Canvi de Categoria:** Es canvien els elements processats a la categoria "processat" a qBittorrent.
6. **Neteja Periòdica:** Passades unes setmanes (quan el ràtio de seeding és suficient), s'esborren els torrents de la categoria "processat" que ja estan aturats.

---

## Anàlisi Tècnica

### Punts Positius (Pros)
*   **Control de Qualitat Total:** L'import manual evita que fitxers mal etiquetats o amb errors de conversió embrutin la base de dades de Plex.
*   **Conservació del Seeding:** En fer una còpia local (`TMP`) per al processament, el client de torrent pot seguir compartint l'original sense bloquejos de fitxer.
*   **Estandardització:** Tot el contingut de la llibreria té un format homogeni, facilitant el "Direct Play" i estalviant CPU al servidor Plex.
*   **Seguretat de Xarxa:** El processament pesat (Handbrake) es fa en disc local, evitant trànsit innecessari d'anada i tornada pel protocol de xarxa (SMB/NFS).

### Punts Negatius i Riscos (Cons)
*   **Càrrega Cognitiva:** Requereix massa intervenció manual (passos 3, 4, 5 i 6). Si s'acumula feina, el workflow esdevé un coll d'ampolla.
*   **Latència de Disponibilitat:** Des que el torrent acaba fins que està a Plex, passa molt de temps a causa de la conversió i l'espera de la intervenció manual.
*   **Duplicitat d'Espai:** Durant el procés, el fitxer existeix en tres llocs: carpeta de torrents (seeding), carpeta TMP (staging) i carpeta final (Plex). Això pot omplir els discos ràpidament si són fitxers 4K.

### És "Overkill"?
**Sí i No.** Per a un usuari normal, sí. Per a un administrador d'Arch Linux amb una llibreria acurada i unitats de xarxa, és un **disseny prudent**. Estàs actuant com un filtre de qualitat (QA) humà.

### Possibles Millores (Futur)
1. **Auto-Tagging:** Es podria automatitzar que l'script, al finalitzar, enviés una comanda a l'API de qBittorrent per canviar la categoria a "processat" automàticament.
2. **Notificacions:** Afegir un bot de Telegram/Discord que avisi quan la conversió ha acabat per reduir el temps d'espera de l'import manual.
3. **Hardware Acceleration:** Assegurar que Handbrake faci servir **NVENC** (NVIDIA) per reduir el temps de conversió de hores a minuts.

---
*Document generat per Gemini CLI el 25/01/2026.*
