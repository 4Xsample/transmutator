"""
Configuration module for Transmutator V2.

Loads configuration from config.yaml if present, falls back to defaults.
Supports reading and writing pipeline_selection and qbittorrent settings.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

CONFIG_FILENAME = "config.yaml"
_PIPELINE_SELECTION_KEYS = ("importar", "convertir", "enviar")
_CATEGORIES_ORDER = ("lidarr", "tv-sonarr", "radarr")  # Música, Sèries, Pel·lícules
_DEFAULT_QBT_HOST = "http://localhost"
_DEFAULT_QBT_PORT = 8080
_DEFAULT_QBT_API_KEY_HEADER = "X-API-Key"


def _expand_path(path_str: str) -> Path:
    """Expand ~ and convert to Path."""
    return Path(os.path.expanduser(path_str))


def _config_path() -> Path:
    return Path(CONFIG_FILENAME)


def _parse_qbt_connection(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize qBittorrent connection settings with backward compatibility."""
    raw_url = str(raw.get("url", "") or "").strip()
    raw_host = str(raw.get("host", "") or "").strip()
    raw_port = raw.get("port", None)

    if raw_url and not raw_host:
        parsed = urlparse(raw_url if "://" in raw_url else f"http://{raw_url}")
        scheme = parsed.scheme or "http"
        hostname = parsed.hostname or "localhost"
        raw_host = f"{scheme}://{hostname}"
        if raw_port in (None, "", 0):
            raw_port = parsed.port or _DEFAULT_QBT_PORT

    host = raw_host or _DEFAULT_QBT_HOST
    try:
        port = int(raw_port or _DEFAULT_QBT_PORT)
    except (TypeError, ValueError):
        port = _DEFAULT_QBT_PORT

    return {
        "enabled": bool(raw.get("enabled", False)),
        "host": host,
        "port": port,
        "url": f"{host.rstrip('/')}:{port}",
        "username": str(raw.get("username", "") or "").strip(),
        "password": str(raw.get("password", "") or "").strip(),
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "api_key_header": str(raw.get("api_key_header", "") or _DEFAULT_QBT_API_KEY_HEADER).strip() or _DEFAULT_QBT_API_KEY_HEADER,
        "processed_category": str(raw.get("processed_category", "") or "processat").strip() or "processat",
        "modify_torrent_category": bool(raw.get("modify_torrent_category", False)),
    }


def _load_config() -> Dict[str, Any]:
    """Load configuration from YAML file or return empty dict."""
    if not YAML_AVAILABLE:
        return {}
    p = _config_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


_CONFIG = _load_config()


def _default_pipeline_selection() -> Dict[str, Dict[str, bool]]:
    """Default: all categories and phases enabled."""
    return {
        cat: {k: True for k in _PIPELINE_SELECTION_KEYS}
        for cat in _CATEGORIES_ORDER
    }


class Config:
    """Configuration class that loads from YAML with defaults."""
    
    # Paths - Load from YAML or use defaults
    _paths = _CONFIG.get("paths", {})
    TORRENT_BASE = _expand_path(_paths.get("torrent_base", "/mnt/Torrent"))
    TMP_STAGING = _expand_path(_paths.get("tmp_staging", "~/Videos/TMP"))
    OUTPUT_BASE = _expand_path(_paths.get("output_base", "~/Videos"))
    PLEX_DESTINATION = _expand_path(_paths.get("plex_destination", "/mnt/PlexMedia/Downloads"))
    
    # Category mappings
    _categories = _CONFIG.get("categories", {})
    TORRENT_CATEGORIES = {
        "tv-sonarr": _categories.get("tv-sonarr", "tv-sonarr"),
        "radarr": _categories.get("radarr", "radarr"),
        "lidarr": _categories.get("lidarr", "lidarr"),
    }
    
    # qBittorrent API settings (updated at runtime by save_qbittorrent_config)
    _qbt = _parse_qbt_connection(_CONFIG.get("qbittorrent", {}))
    QBITTORRENT_ENABLED = _qbt["enabled"]
    QBITTORRENT_HOST = _qbt["host"]
    QBITTORRENT_PORT = _qbt["port"]
    QBITTORRENT_URL = _qbt["url"]
    QBITTORRENT_USERNAME = _qbt["username"]
    QBITTORRENT_PASSWORD = _qbt["password"]
    QBITTORRENT_API_KEY = _qbt["api_key"]
    QBITTORRENT_API_KEY_HEADER = _qbt["api_key_header"]
    PROCESSED_CATEGORY = _qbt["processed_category"]
    MODIFY_TORRENT_CATEGORY = _qbt["modify_torrent_category"]
    
    # Video settings
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm"}
    _video = _CONFIG.get("video", {})
    VIDEO_PRESET_MOVIES = _video.get("preset_movies", "4Xmovie")
    VIDEO_PRESET_SERIES = _video.get("preset_series", "4Xseries")
    VIDEO_TARGET_RESOLUTION = _video.get("target_resolution", "1080p")
    
    # Audio settings
    AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".aiff", ".m4a", ".aac"}
    AUDIO_LOSSY_EXTENSIONS = {".mp3", ".aac", ".ogg", ".m4a"}
    AUDIO_LOSSLESS_EXTENSIONS = {".flac", ".wav", ".aiff"}
    _audio = _CONFIG.get("audio", {})
    AUDIO_TARGET_BITRATE = _audio.get("target_bitrate", "320k")
    AUDIO_TARGET_FORMAT = _audio.get("target_format", "mp3")
    
    # HandBrake settings
    _tools = _CONFIG.get("tools", {})
    HANDBRAKE_CLI = _tools.get("handbrake_cli", "HandBrakeCLI")
    _presets_path = _tools.get("handbrake_presets_path", "~/.config/ghb/presets.json")
    HANDBRAKE_PRESETS_PATH = _expand_path(_presets_path)
    
    # FFmpeg settings
    FFMPEG_BIN = _tools.get("ffmpeg", "ffmpeg")
    
    @classmethod
    def get_torrent_path(cls, category: str) -> Path:
        """Get the torrent source path for a category."""
        mapped = cls.TORRENT_CATEGORIES.get(category, category)
        return cls.TORRENT_BASE / mapped
    
    @classmethod
    def get_tmp_path(cls, category: str) -> Path:
        """Get the temporary staging path for a category."""
        return cls.TMP_STAGING / category
    
    @classmethod
    def get_output_path(cls, category: str) -> Path:
        """Get the output path for processed files."""
        if category == "lidarr":
            return cls.OUTPUT_BASE.parent / "Music"
        elif category == "radarr":
            return cls.OUTPUT_BASE / "radarr"
        elif category == "tv-sonarr":
            return cls.OUTPUT_BASE / "sonarr"
        else:
            return cls.OUTPUT_BASE / category
    
    @classmethod
    def get_plex_path(cls, category: str) -> Path:
        """Get the final Plex destination path."""
        if category == "lidarr":
            return cls.PLEX_DESTINATION / "Music"
        else:
            return cls.PLEX_DESTINATION
    
    @classmethod
    def validate_paths(cls) -> Dict[str, bool]:
        """Validate that all configured paths exist or can be created."""
        results = {}
        
        # Check if base paths exist
        results["torrent_base"] = cls.TORRENT_BASE.exists()
        results["tmp_staging"] = cls.TMP_STAGING.exists() or cls.TMP_STAGING.parent.exists()
        results["plex_destination"] = cls.PLEX_DESTINATION.exists()
        
        # Check if tools are available
        import shutil
        results["handbrake_available"] = shutil.which(cls.HANDBRAKE_CLI) is not None
        results["ffmpeg_available"] = shutil.which(cls.FFMPEG_BIN) is not None
        
        return results


# ── Paths (for API / Web UI) ───────────────────────────────────────────


def get_paths_config() -> Dict[str, str]:
    """Return paths section for API (values as strings)."""
    return {
        "torrent_base": str(Config.TORRENT_BASE),
        "tmp_staging": str(Config.TMP_STAGING),
        "output_base": str(Config.OUTPUT_BASE),
        "plex_destination": str(Config.PLEX_DESTINATION),
    }


def save_paths_config(values: Dict[str, Any]) -> None:
    """Write paths to config.yaml (merge). Update Config in memory."""
    global _CONFIG
    if not YAML_AVAILABLE:
        return
    path = _config_path()
    config = _load_config() if path.exists() else {}
    config.setdefault("paths", {})
    for key in ("torrent_base", "tmp_staging", "output_base", "plex_destination"):
        if key in values and values[key] is not None:
            config["paths"][key] = str(values[key]).strip()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception:
        return
    _CONFIG = config
    _paths = config.get("paths", {})
    Config.TORRENT_BASE = _expand_path(_paths.get("torrent_base", "/mnt/Torrent"))
    Config.TMP_STAGING = _expand_path(_paths.get("tmp_staging", "~/Videos/TMP"))
    Config.OUTPUT_BASE = _expand_path(_paths.get("output_base", "~/Videos"))
    Config.PLEX_DESTINATION = _expand_path(_paths.get("plex_destination", "/mnt/PlexMedia/Downloads"))


# ── Pipeline selection (pantalla inicial) ──────────────────────────────


def get_pipeline_selection() -> Dict[str, Dict[str, bool]]:
    """Return pipeline_selection from config: category -> { importar, convertir, enviar }."""
    raw = _CONFIG.get("pipeline_selection") or {}
    result = {}
    for cat in _CATEGORIES_ORDER:
        sub = raw.get(cat) or {}
        result[cat] = {
            k: bool(sub.get(k, True)) for k in _PIPELINE_SELECTION_KEYS
        }
    return result


def save_pipeline_selection(selection: Dict[str, Dict[str, bool]]) -> None:
    """Write pipeline_selection to config.yaml (merge with existing). Persist on every change."""
    global _CONFIG
    if not YAML_AVAILABLE:
        return
    path = _config_path()
    config = _load_config() if path.exists() else {}
    config["pipeline_selection"] = {
        cat: {k: selection[cat][k] for k in _PIPELINE_SELECTION_KEYS}
        for cat in _CATEGORIES_ORDER
        if cat in selection
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception:
        pass
    else:
        _CONFIG = config


# ── qBittorrent i categories (popup configuració) ────────────────────────


def get_qbittorrent_config() -> Dict[str, Any]:
    """Return current qBittorrent and categories for the config UI."""
    qbt = _parse_qbt_connection(_CONFIG.get("qbittorrent") or {})
    cats = _CONFIG.get("categories") or {}
    return {
        "enabled": qbt["enabled"],
        "host": qbt["host"],
        "port": qbt["port"],
        "url": qbt["url"],
        "username": qbt["username"],
        "password": qbt["password"],
        "api_key": qbt["api_key"],
        "api_key_header": qbt["api_key_header"],
        "processed_category": qbt["processed_category"],
        "modify_torrent_category": qbt["modify_torrent_category"],
        "categories": {
            "lidarr": cats.get("lidarr", "lidarr"),
            "tv-sonarr": cats.get("tv-sonarr", "tv-sonarr"),
            "radarr": cats.get("radarr", "radarr"),
        },
    }


def save_qbittorrent_config(values: Dict[str, Any]) -> None:
    """Write qbittorrent and categories to config.yaml (merge). Update Config in memory."""
    global _CONFIG
    if not YAML_AVAILABLE:
        return
    path = _config_path()
    config = _load_config() if path.exists() else {}
    config.setdefault("qbittorrent", {})
    host = str(values.get("host", "") or _DEFAULT_QBT_HOST).strip() or _DEFAULT_QBT_HOST
    try:
        port = int(values.get("port", "") or _DEFAULT_QBT_PORT)
    except (TypeError, ValueError):
        port = _DEFAULT_QBT_PORT
    config["qbittorrent"]["enabled"] = bool(values.get("enabled", False))
    config["qbittorrent"]["host"] = host
    config["qbittorrent"]["port"] = port
    config["qbittorrent"]["url"] = f"{host.rstrip('/')}:{port}"
    config["qbittorrent"]["username"] = str(values.get("username", "") or "").strip()
    config["qbittorrent"]["password"] = str(values.get("password", "") or "").strip()
    config["qbittorrent"]["api_key"] = str(values.get("api_key", "") or "").strip()
    config["qbittorrent"]["api_key_header"] = str(
        values.get("api_key_header", "") or _DEFAULT_QBT_API_KEY_HEADER
    ).strip() or _DEFAULT_QBT_API_KEY_HEADER
    config["qbittorrent"]["processed_category"] = str(
        values.get("processed_category", "") or "processat"
    ).strip() or "processat"
    config["qbittorrent"]["modify_torrent_category"] = bool(values.get("modify_torrent_category", False))
    config.setdefault("categories", {})
    for key in _CATEGORIES_ORDER:
        if key in values.get("categories", {}):
            config["categories"][key] = str(values["categories"][key] or key).strip() or key
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception:
        return
    _CONFIG = config
    # Update Config class so running app sees new values
    qbt = _parse_qbt_connection(config.get("qbittorrent", {}))
    Config.QBITTORRENT_ENABLED = qbt["enabled"]
    Config.QBITTORRENT_HOST = qbt["host"]
    Config.QBITTORRENT_PORT = qbt["port"]
    Config.QBITTORRENT_URL = qbt["url"]
    Config.QBITTORRENT_USERNAME = qbt["username"]
    Config.QBITTORRENT_PASSWORD = qbt["password"]
    Config.QBITTORRENT_API_KEY = qbt["api_key"]
    Config.QBITTORRENT_API_KEY_HEADER = qbt["api_key_header"]
    Config.PROCESSED_CATEGORY = qbt["processed_category"]
    Config.MODIFY_TORRENT_CATEGORY = qbt["modify_torrent_category"]
    Config.TORRENT_CATEGORIES = {
        k: config.get("categories", {}).get(k, k) for k in _CATEGORIES_ORDER
    }
