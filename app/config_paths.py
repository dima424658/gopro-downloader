"""Operating-system paths for GoPro application configuration and data."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

APP_DIR_NAME = "gopro-downloader"
CONFIG_FILENAME = "config.json"
COHN_DB_FILENAME = "cohn_db.json"
THUMBNAIL_DIR_NAME = "thumbnails"


def get_os_config_dir(platform_name: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Return the user configuration root, honoring XDG and Windows conventions."""
    platform_name = os.name if platform_name is None else platform_name
    env = os.environ if env is None else env
    if platform_name == "nt":
        return Path(env.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"])
    return Path(env.get("HOME") or Path.home()) / ".config"


def get_config_path(platform_name: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Return the application-specific configuration directory."""
    return get_os_config_dir(platform_name, env) / APP_DIR_NAME


def get_config_file(platform_name: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Return the application preferences file path."""
    return get_config_path(platform_name, env) / CONFIG_FILENAME


def get_cohn_db_path(platform_name: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Return the Open GoPro COHN database path."""
    return get_config_path(platform_name, env) / COHN_DB_FILENAME


def get_thumbnail_cache_path(platform_name: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    """Return the cached media thumbnails directory."""
    return get_config_path(platform_name, env) / THUMBNAIL_DIR_NAME


CONFIG_PATH = get_config_path()
CONFIG_FILE = get_config_file()
COHN_DB_PATH = get_cohn_db_path()
THUMBNAIL_CACHE_PATH = get_thumbnail_cache_path()
