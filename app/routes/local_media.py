"""Operations on downloaded media files."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, jsonify

from ..cohn import checked_filename
from ..settings import default_media_directory, read_desktop_settings, resolve_app_path
from .helpers import optional_text, request_data

blueprint = Blueprint("local_media_api", __name__)


def _media_path(media_dir: str, filename: str) -> Path:
    camera_filename = checked_filename(filename)
    root = resolve_app_path(media_dir, str(default_media_directory())).resolve()
    candidate = (root / Path(camera_filename).name).resolve()
    if candidate.parent != root:
        raise ValueError("Invalid local file path.")
    return candidate


def _configured_media_directory(payload: dict[str, object]) -> str:
    settings = read_desktop_settings()
    return optional_text(payload, "media_dir") or settings["media_dir"] or str(default_media_directory())


@blueprint.post("/api/local-media/status")
def local_media_status():
    payload = request_data()
    filenames = payload.get("filenames")
    if not isinstance(filenames, list) or any(not isinstance(name, str) for name in filenames):
        return jsonify(error="Invalid file list."), 400
    if len(filenames) > 1000:
        return jsonify(error="Too many files."), 400
    try:
        media_dir = _configured_media_directory(payload)
        files = {name: _media_path(media_dir, name).is_file() for name in filenames}
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(files=files)


@blueprint.post("/api/local-media/open")
def open_local_media():
    payload = request_data()
    filename = payload.get("filename")
    if not isinstance(filename, str) or not filename:
        return jsonify(error="No file specified."), 400
    try:
        path = _media_path(_configured_media_directory(payload), filename)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if not path.is_file():
        return jsonify(error="Local copy of the file was not found."), 404
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        return jsonify(error=f"Could not open file: {exc}"), 500
    return jsonify(opened=True)


@blueprint.post("/api/local-media/delete")
def delete_local_media():
    payload = request_data()
    filename = payload.get("filename")
    if not isinstance(filename, str) or not filename:
        return jsonify(error="No file specified."), 400
    try:
        path = _media_path(_configured_media_directory(payload), filename)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if not path.is_file():
        return jsonify(error="Local copy of the file was not found."), 404
    try:
        path.unlink()
    except OSError as exc:
        return jsonify(error=f"Could not delete local file: {exc}"), 500
    return jsonify(deleted=True)
