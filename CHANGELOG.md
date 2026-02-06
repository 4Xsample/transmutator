# Changelog

Tots els canvis notables del projecte es documenten aquí.

El format es basa en [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/).

## [0.8.0] - 2026-02-06

### Afegit

- **Report final (Fase 3)**
  - Pantalla modal post-pipeline amb quadre d'èxits (fitxer, mida, estalvi, temps) i quadre d'errors.
  - Botó «Guardar Report» per exportar el report a `~/transmutator_report_YYYYMMDD_HHMMSS.md`.
  - Report TUI i export Markdown amb amplada dinàmica segons la mida del terminal.
- **Efectes CRT**
  - Tint phosphor (#4AEF98 4%) a la pantalla.
  - Marc de monitor (heavy border) al contenidor principal.
- **Countdown entre fases**
  - Resum amb categories alineades: Pel·lícules / Episodis / Cançons (i TOTAL).
  - Columnes numèriques alineades a la dreta.
- **Progrés HandBrake en temps real**
  - Suport per JSON multilínia (HandBrake 1.10+: «Progress: { ... }»).
  - Execució amb pseudo-TTY (Unix) per forçar line-buffering i rebre updates sense bloquejar.
  - Throttle d’actualitzacions UI: com a màxim cada 1 s o cada 1% per mantenir la conversió fluida.
  - Presets custom via `--preset-import-file` (config HandBrake).
  - Variable d’entorn `TRANSMUTATOR_DEBUG_HANDBRAKE=1` per escriure stdout/stderr a `handbrake_debug.log`.
- **Label de progrés (fase convertir)**
  - Format: nom | mida | % | ETA (nom truncat, sufix sempre visible).
  - Reserva mínima d’espai per al sufix perquè mida i ETA no es tallin.
- **Animació de transició**
  - Durada configurable (~9 s per defecte) abans del countdown.

### Canviat

- Parser de progrés HandBrake: accepta JSON per stderr; parser de text més permisiu (qualsevol línia amb %).
- Countdown de conversió: 10 s; animació pre-report ~9 s.

### Corregit

- Progrés durant la conversió no s’actualitzava perquè HandBrake envia JSON multilínia; ara s’acumulen línies fins a objecte complet.
- Barres de progrés per fitxer saltaven de 0% a 100% per buffering; mitigat amb pty i throttle.

---

[0.8.0]: https://github.com/4Xsample/transmutator/releases/tag/v0.8.0
