# Pipboy-Transfer — Interfície web per Transmutator

Interfície web (React + TypeScript + Vite) amb estètica Pip-Boy per al pipeline Transmutator.

## Contingut

- **client/** — Frontend: pàgines Home (selecció Import/Convert/Send per categoria), Settings, ProcessPage, ReportPage.
- **server/** — Backend Node/Express (actualment sense rutes d’API enllaçades al pipeline Python).
- **shared/** — Esquema compartit (Drizzle).

## Com executar

```bash
cd Pipboy-Transfer
npm install
npm run dev
```

Obre el navegador a la URL que indiqui Vite (normalment `http://localhost:5000`).

## Integració amb Transmutator

El backend Python (TUI) és la font de veritat del pipeline. Per usar aquesta UI com a frontend:

1. Exposar una API REST (o WebSocket) des del projecte Python (`src/`) que exposi escaneig, iniciar/aturar pipeline i estat.
2. En aquest projecte, canviar `server/routes.ts` (i el que calgui) per cridar eixa API en lloc de lògica local.

Fins llavors, la UI és un prototip visual/UX per al mateix flux (Import → Convert → Send).
