# Transmutator V2: Vision & Requirements

Aquesta és la proposta per evolucionar el pipeline de scripts Bash cap a una aplicació Python robusta amb interfície de terminal (TUI).

## 1. Pilars Tècnics
*   **Estètica:** TUI (Terminal User Interface) inspirada en el **Pip-Boy de Fallout 4**. Color predominant verd/ambre monocromàtic, ús de caràcters ASCII per a l'estructura i estil retro-futurista.
*   **Estratègia de Transcoding:**
    *   Prioritat: **Fast Decoding** (fitxers més fàcils de digerir per a clients antics).
    *   Resolució: Tot a **1080p** (estalvi d'espai i compatibilitat).
    *   Eina: HandBrakeCLI/FFmpeg (amb configuració per optimitzar la qualitat/compatibilitat vs velocitat).

## 2. Característiques Principals
### A. Configuració
*   Gestió de rutes (Origen, TMP, Destí).
*   Integració amb qBittorrent via API (URL, clau API) per a l'auto-tagging (categoria "processat").

### B. Interfície de Processament (TUI)
*   **Indicadors d'estat:** Fase actual (Importar, Convertir, Enviar).
*   **Comptadors:** Arxius totals, fets i restants.
*   **Llista scrollable:** Tots els arxius amb marcadors d'estat (pendent, fent, completat).
*   **Barra de progrés detallada:** Per a l'arxiu actual amb percentatge i ETA (temps estimat).
*   **Controls:** Botons de Pausa i Stop (Graceful shutdown).

### C. Report Final
*   **Pantalla de resum:** Dos quadres de text adjacents (Èxits vs. Errors).
*   **Dades d'èxit (Info "inútil" però curiosa):** Nom d'arxiu, mida original, mida final, temps de transcode.
*   **Dades d'error:** Missatge d'error de cada fitxer fallit.
*   **Accions:** Guardar report a disc i tancar.

## 3. Descripció Literal de l'Usuari (Matisos i Context)
> "la velositat de transcoding actual es un compromis entre el que vull i el que puc. el meu servidor plex es molt poc potent pero tb ho son alguns dels dispositius que ho reprodueixen com el meu apple tv HD... simplement es una merda procesant arxius amb nvenc per que no te hardware decoding per a aquest format. A mes, si et fixes el valor per triar entre fast encoding o fast decoding el tinc lleugerament cap a fast decoding, fa mes lenta la meva codificació pero son arxius de molta mes qualitat i mes facils de digerir per tota mena de clients. i encara que algun dels arxius que processo esta descarregat com a 2k o 4k, tot ho passo a 1080 per que soc pobre i no tinc l'espai que necessitaria per posar massivament contingut en 4K i el temps en que els arxius estan a plex i essent seedejats... doncs es el preu que pago per el contingut. Sobre l'autotagging si, es algo en el que havia pensat i no ha de ser dificil, ens baixem la llibreria qbitorrent-api i ja tindriem la feina quasi feta. i ara et presento la idea del projecte transmutator. El que vull fer es fer un py que faci aixo pero en guai. amb una tui decent amb una estetica a lo pipboy de fallout4, que em permeti seleccionar les opcions comodement, que em permeti definir les carpetes al menu de config, la url del qbitorrent i la clau api, (tot i que per començar sense complicar-nos podriem hardcodejar-ho que ja em va be) i que quan arrenquem el progres vagi marcant en quina fase estem (importar, convertir o enviar) quants arxius processarem, cuants arxius queden per processar i quants hem fet, una llista scrollable amb tots els arxius (podria servir per marcar quins tenim fets quin estem fent i quins queden per fer) una barra de progres per al proces actual, la pelicula, serie o el que sigui que estem convertint en aquells moments, amb percentatge i eta) botó de pausa o stop. una pantalla final amb els missatges pertinents, success o fail amb un scroll dels exits per una banda amb info curiosa pero inutil del pal arxiu, mida original, mida final, temps de transcode, etc. i una llista dels fails amb el missatge d'error de cada fallo aixi en 2 quadres de text un al costat de l'altre. i el botó de guardar el report aquest i el de tancar."

---
*Document actualitzat el 25/01/2026.*