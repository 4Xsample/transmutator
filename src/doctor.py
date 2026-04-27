"""
Environment diagnostics for Transmutator.

Arch Linux tends to move Python quickly, so the goal here is to make it easy
to distinguish project bugs from environment drift.
"""

from __future__ import annotations

import importlib
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from .config import Config


def _venv_python_path() -> Path:
    return Path(__file__).resolve().parent.parent / "venv" / "bin" / "python"


def _check_module(name: str) -> Tuple[bool, str]:
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "unknown")
        return True, str(version)
    except Exception as exc:
        return False, str(exc)


def collect_diagnostics() -> Dict[str, object]:
    modules_to_check = [
        "textual",
        "rich",
        "yaml",
        "fastapi",
        "uvicorn",
    ]
    module_results = {name: _check_module(name) for name in modules_to_check}

    tools = {
        "HandBrakeCLI": shutil.which(Config.HANDBRAKE_CLI),
        "ffmpeg": shutil.which(Config.FFMPEG_BIN),
        "rsync": shutil.which("rsync"),
        "node": shutil.which("node"),
        "npm": shutil.which("npm"),
    }

    frontend_dist = Path(__file__).resolve().parent.parent / "Pipboy-Transfer" / "dist" / "public" / "index.html"
    venv_python = _venv_python_path()

    warnings: List[str] = []
    if not hasattr(sys, "base_prefix") or sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        warnings.append("Python actual fora de venv del projecte.")
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        warnings.append("No s'està usant /venv/bin/python del projecte.")
    if not frontend_dist.exists():
        warnings.append("Frontend web no buildat encara (falta dist/public/index.html).")
    for name, (ok, _) in module_results.items():
        if not ok:
            warnings.append(f"Modul Python no disponible: {name}.")
    if tools["HandBrakeCLI"] is None:
        warnings.append("HandBrakeCLI no trobat al PATH.")
    if tools["ffmpeg"] is None:
        warnings.append("ffmpeg no trobat al PATH.")

    return {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "venv_python": str(venv_python),
        "config_path": str((Path.cwd() / "config.yaml").resolve()),
        "config_exists": (Path.cwd() / "config.yaml").exists(),
        "module_results": module_results,
        "tools": tools,
        "frontend_built": frontend_dist.exists(),
        "warnings": warnings,
    }


def render_diagnostics() -> str:
    data = collect_diagnostics()
    lines = [
        "== Transmutator Doctor ==",
        "",
        f"Sistema:         {data['platform']}",
        f"Python:          {data['python_version']}",
        f"Executable:      {data['python_executable']}",
        f"Venv esperat:    {data['venv_python']}",
        f"Config.yaml:     {'OK' if data['config_exists'] else 'MISSING'} ({data['config_path']})",
        f"Frontend build:  {'OK' if data['frontend_built'] else 'MISSING'}",
        "",
        "Moduls Python:",
    ]

    for name, (ok, detail) in data["module_results"].items():
        status = "OK" if ok else "MISSING"
        lines.append(f"  - {name:<10} {status}  {detail}")

    lines.append("")
    lines.append("Eines externes:")
    for name, path in data["tools"].items():
        lines.append(f"  - {name:<10} {'OK' if path else 'MISSING'}  {path or '-'}")

    warnings = data["warnings"]
    lines.append("")
    if warnings:
        lines.append("Avisos:")
        for warning in warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("Avisos: cap")

    return "\n".join(lines)
