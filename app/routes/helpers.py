"""Shared request parsing and path helpers for the web layer."""

from __future__ import annotations

from typing import Any

from flask import request

from ..cohn import OperationArgs
from ..config_paths import CONFIG_PATH
from ..settings import default_media_directory, read_desktop_settings, resolve_app_path


def request_data() -> dict[str, Any]:
    """Return a JSON object payload, ignoring non-object or invalid JSON bodies."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def optional_text(payload: dict[str, Any], key: str) -> str | None:
    """Return a trimmed string field or None when the payload value is not text."""
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    return value.strip() or None


def operation_args(payload: dict[str, Any]) -> OperationArgs:
    settings = read_desktop_settings()
    password = payload.get("wifi_password")
    return OperationArgs(
        target=optional_text(payload, "target"),
        ssid=optional_text(payload, "ssid"),
        wifi_password=password if isinstance(password, str) and password else None,
        output_dir=resolve_app_path(
            optional_text(payload, "output_dir"),
            settings["cohn_dir"] or str(CONFIG_PATH),
        ),
        media_dir=resolve_app_path(
            optional_text(payload, "media_dir"),
            settings["media_dir"] or str(default_media_directory()),
        ),
    )
