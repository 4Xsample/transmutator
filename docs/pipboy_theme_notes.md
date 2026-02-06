# Notes: estètica Pip-Boy / Fallout 4 Terminal

Extret del tema **Fallout 4 Terminal** (Discord) per Bates.  
Font: [Fallout4TerminalTheme](https://github.com/B4T3S/Fallout4TerminalTheme) · [web](https://B4T3S.github.io/Fallout4TerminalTheme)

Aquest document recull la paleta i idees reutilitzables per la TUI de Transmutator (Textual).

---

## Paleta de colors (RGB → ús a TUI)

| Variable / rol      | RGB             | Hex       | Ús suggerit a TUI                          |
|--------------------|-----------------|-----------|--------------------------------------------|
| Highlight / text   | 74, 239, 152    | `#4AEF98` | Text principal, accents, marques           |
| Background         | 0, 9, 0         | `#000900` | Fons general                               |
| Close / deny       | 212, 18, 39     | `#D41227` | Errors, botó Stop, “tancar”                |
| Online / ok        | 57, 255, 20     | `#39FF14` | Èxit, completat, “online”                  |
| Idle / AFK         | 255, 255, 51    | `#FFFF33` | Advertències, en espera, idle              |
| DND                | 255, 0, 0       | `#FF0000` | Alerta, DND                                |
| Streaming / extra  | 188, 19, 254    | `#BC13FE` | Accent secundari (opcional)                |

- **Text principal i highlight** coincideixen (verd Pip-Boy).
- **Fons**: negre amb molt de verd (`#000900`) per no ser negre pur.
- Per **Textual** es poden definir com a `Color` o al CSS del tema (ex. `primary`, `background`, `error`, `warning`, `success`).

---

## Semàntica per la TUI

- **Fons**: `#000900`
- **Text / primary**: `#4AEF98`
- **Èxit / completat**: `#39FF14`
- **Advertència / idle / en curs**: `#FFFF33`
- **Error / stop / tancar**: `#D41227` (o `#FF0000` si es vol més fort)
- **Accent secundari** (opcional): `#BC13FE`

Transició/animació al tema original: `0.3s` — a TUI es pot reflectir en delays o “blink” si el framework ho permet.

---

## Efectes esmentats al tema

- **CRT effect**: el tema importa `crtEffect.css`. A TUI es pot aproximar amb:
  - línies horitzontals subtils (scanlines) amb caràcters o estil de línia,
  - o capa semitransparent amb patró si Textual ho suporta.
- **Títol / branding**: “4Xsample Industries (tm)” — per a la TUI es pot usar una capçalera similar (ex. “4Xsample Industries” o “Transmutator”) en verd Pip-Boy.

---

## Resum per implementació (Textual)

1. Definir tema amb `primary` = `#4AEF98`, `background` = `#000900`.
2. Mapear `success` → `#39FF14`, `warning` → `#FFFF33`, `error` → `#D41227`.
3. Opcional: accent secundari `#BC13FE` per destacar elements.
4. Considerar “scanlines” o efecte CRT només si es pot fer sense sobrecarregar la terminal.
5. Capçalera tipus terminal (4Xsample Industries / Transmutator) amb el mateix verd.

---

*Document generat a partir de `Fallout4Terminal.theme.css` (eliminat de l’arrel del projecte).*
