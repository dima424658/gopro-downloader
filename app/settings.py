"""Persistent desktop preferences and saved COHN state."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .config_paths import CONFIG_FILE, CONFIG_PATH
from .resources import RESOURCE_DIR


def default_media_directory() -> Path:
    """Return the user's standard Downloads folder with a GoPro subdirectory."""
    home = Path.home()
    downloads = home / "Downloads"
    return downloads / "GoPro"


def ensure_config_directory() -> Path:
    """Create the private user config directory."""
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_PATH.chmod(0o700)
    except OSError:
        pass
    return CONFIG_PATH


def _write_config(value: dict[str, Any]) -> None:
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_PATH,
            prefix=f"{CONFIG_FILE.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, CONFIG_FILE)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def resolve_app_path(value: str | None, default: str) -> Path:
    """Resolve relative user paths from the project directory, not process CWD."""
    path = Path(value or default).expanduser()
    return path if path.is_absolute() else RESOURCE_DIR / path


def read_desktop_settings() -> dict[str, str | None]:
    ensure_config_directory()
    try:
        value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    media_dir = value.get("media_dir") if isinstance(value, dict) else None
    cohn_dir = value.get("cohn_dir") if isinstance(value, dict) else None
    theme = value.get("theme") if isinstance(value, dict) else None
    wifi_ssid = value.get("wifi_ssid") if isinstance(value, dict) else None
    default_downloads = str(default_media_directory())
    settings = {
        "media_dir": (
            media_dir
            if isinstance(media_dir, str) and media_dir.strip() and media_dir.strip() != "media"
            else default_downloads
        ),
        "cohn_dir": cohn_dir if isinstance(cohn_dir, str) and cohn_dir.strip() else str(CONFIG_PATH),
        "theme": theme if isinstance(theme, str) and theme in {"light", "dark"} else None,
        "wifi_ssid": wifi_ssid if isinstance(wifi_ssid, str) and wifi_ssid.strip() else None,
    }
    if not CONFIG_FILE.exists() or media_dir == "media":
        _write_config(settings)
    return settings


def write_desktop_settings(updates: dict[str, Any]) -> dict[str, str | None]:
    settings = read_desktop_settings()
    if "media_dir" in updates:
        media_dir = updates["media_dir"]
        if not isinstance(media_dir, str) or not media_dir.strip():
            raise ValueError("Specify a download folder.")
        settings["media_dir"] = media_dir.strip()
    if "cohn_dir" in updates:
        cohn_dir = updates["cohn_dir"]
        if not isinstance(cohn_dir, str) or not cohn_dir.strip():
            raise ValueError("Specify the camera configuration folder.")
        settings["cohn_dir"] = cohn_dir.strip()
    if "theme" in updates:
        theme = updates["theme"]
        if not isinstance(theme, str) or theme not in {"light", "dark"}:
            raise ValueError("Unknown theme.")
        settings["theme"] = theme
    if "wifi_ssid" in updates:
        wifi_ssid = updates["wifi_ssid"]
        if not isinstance(wifi_ssid, str) or not wifi_ssid.strip():
            raise ValueError("Invalid Wi-Fi network name.")
        settings["wifi_ssid"] = wifi_ssid.strip()
    _write_config(settings)
    return settings


def has_saved_cohn(path: Path | None = None) -> bool:
    """Return whether the local SDK database contains complete credentials."""
    ensure_config_directory()
    if path is None:
        settings = read_desktop_settings()
        path = resolve_app_path(settings["cohn_dir"], str(CONFIG_PATH)) / "cohn_db.json"
    try:
        database = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    required = ("ip_address", "username", "password", "certificate")
    return any(
        all((credentials or {}).get(key) for key in required)
        for table in database.values()
        if isinstance(table, dict)
        for record in table.values()
        if isinstance(record, dict)
        for credentials in (record.get("credentials"),)
        if isinstance(credentials, dict)
    )
