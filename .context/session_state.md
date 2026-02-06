# Transmutator V2 — Context de Sessió

## Versió actual: v0.8.0 (Fase 3 completada)

## Arquitectura

```
src/
  app.py          — TUI principal (Textual 7.5.0). Worker thread per pipeline.
  widgets.py      — DualColumnList, SegmentedBar, CountdownScreen, ReportScreen. Rich markup (no Text objects).
  hacker.py       — Animació terminal entre fases (cites + dades tècniques). Fases: transform, load, report.
  pipeline.py     — ExtractPhase/LoadPhase. Callback: (category, filename, percent).
  converter.py    — VideoConverter/AudioConverter/MediaConverter + ProcessHandle (SIGSTOP/SIGKILL).
  file_detector.py — FileDetector.scan_all_categories() + scan_torrent_sources().
  report.py       — ReportData, build_report_tui(), generate_report_markdown(), save_report().
  config.py       — Config YAML amb fallbacks.
  tui_theme.css   — Pip-Boy palette (#4AEF98 bright, #2d8a4e mid, #1a3a1a dim) + CRT effects.
  __init__.py     — __version__ = "0.8.0"

tests/ — 109 tests (pytest). test_pipeline, test_process_handle, test_widgets, test_file_detector, test_report.
```

## Decisions tècniques importants

- **Textual 7.5.0**: Static.update() passa per `visualize()` → Visual/Content.
  No usar `rich.text.Text` directament. Tots els renders retornen `str` amb Rich markup.
  NO sobreescriure `_render()` (col·lisió amb Static._render → Visual). Usar `_build()` o similar.
- **Amplada dinàmica**: `self.size.width` + `on_resize()` per repintar. Fallback 80.
- **ProcessHandle**: SIGSTOP/SIGCONT/SIGKILL via os.killpg amb start_new_session=True.
- **Pipeline flow**: Extract → animació → countdown → Transform → animació → countdown → Load → animació report → ReportScreen.
  Sincronització worker↔UI via `threading.Event` per al countdown.
- **ReportScreen**: pantalla modal post-pipeline. Mostra èxits/errors/estadístiques en Rich markup.
  Dismiss amb "save" (app guarda .md) o "close".
- **report.py**: `ReportData` encapsula resultats + comptadors extract/load.
  `build_report_tui()` genera Rich markup, `generate_report_markdown()` genera .md.
  `save_report()` escriu a ~/transmutator_report_YYYYMMDD_HHMMSS.md.
- **CRT effects**: `Screen { tint: #4AEF98 4%; }` per phosphor glow. `#main-container { border: heavy #1a3a1a; }` per marc CRT.
- **HandBrake progress**: HandBrake 1.10+ envia JSON multilínia ("Progress: { ... }"); _collect_multiline_json() acumula línies fins a `}`. Execució amb pty (Unix) per line-buffering. Throttle a l'app: 1s o 1% per no inundar la UI. Debug: TRANSMUTATOR_DEBUG_HANDBRAKE=1 → handbrake_debug.log.
- **rsync parsing**: línies indentades amb % = progrés, no indentades = filename.
- **Idioma**: documentació i UI en català. Codi i comments en anglès.

## Propera fase: Fase 4 (v1.0)

1. Refactorització de codi i neteja de deute tècnic.
2. Menú de configuració interactiu.
3. Documentació final de l'usuari.

## Patrons del repo

- License: MIT modificada en català (fitxer LICENSE).
- README: taula de badges al header, disclaimer al footer.
- Funding: .github/FUNDING.yml (patreon, ko_fi, paypal).
- Commits: en català, descriptius, versió al títol.
- Releases: via `gh release create` amb notes detallades.
