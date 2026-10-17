"""Camera media listing, transfer, deletion, and thumbnail endpoints."""

from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, abort, jsonify, send_file

from ..cohn import media_operation
from ..jobs import start_job
from ..media import delete_camera_media, download_media, download_media_batch, get_media_metadata
from ..thumbnails import THUMBNAIL_CACHE, cache_thumbnails
from .helpers import operation_args, request_data

blueprint = Blueprint("media_api", __name__)


@blueprint.post("/api/media")
def start_media_operation():
    payload = request_data()
    command = payload.get("command")
    if not isinstance(command, str) or command not in {
        "list-media",
        "download",
        "download-many",
        "thumbnail",
        "delete",
    }:
        return jsonify(error="Unknown command."), 400
    filename = payload.get("filename")
    filename = filename if isinstance(filename, str) else None
    filenames = payload.get("filenames")
    if command == "download-many":
        if (
            not isinstance(filenames, list)
            or not filenames
            or len(filenames) > 1000
            or any(not isinstance(name, str) or not name for name in filenames)
        ):
            return jsonify(error="Select between 1 and 1000 files to download."), 400
        filenames = list(dict.fromkeys(filenames))
    if command not in {"list-media", "download-many"} and not filename:
        return jsonify(error="Select a file."), 400
    args = operation_args(payload)
    labels = {
        "list-media": "Loading file list",
        "download": "Downloading original",
        "download-many": "Downloading selected files",
        "thumbnail": "Downloading thumbnail",
        "delete": "Deleting camera file",
    }

    async def list_operation(_: str) -> list[str]:
        return await media_operation(args)

    async def download_operation(job_id: str) -> Path:
        return await download_media(job_id, args, command, filename)

    async def batch_download_operation(job_id: str) -> None:
        await download_media_batch(job_id, args, filenames)

    async def delete_operation(_: str) -> str:
        await delete_camera_media(args, filename)
        return filename or ""

    if command == "list-media":
        operation = list_operation
        initial = {"command": "list-media"}
    elif command == "download-many":
        operation = batch_download_operation
        initial = {
            "command": command,
            "filenames": filenames,
            "cooperative_cancel": True,
            "progress": {"percent": 0},
        }
    elif command == "delete":
        operation = delete_operation
        initial = {"filename": filename, "command": command}
    else:
        operation = download_operation
        initial = {
            "cooperative_cancel": True,
            "progress": {"filename": filename, "percent": 0},
            "filename": filename,
            "command": command,
        }
    job_id, error = start_job(labels[command], operation, initial)
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.post("/api/media/metadata")
def start_media_metadata():
    payload = request_data()
    filename = payload.get("filename")
    if not isinstance(filename, str) or not filename:
        return jsonify(error="Select a file."), 400
    args = operation_args(payload)
    job_id, error = start_job(
        "Loading file information",
        lambda _: get_media_metadata(args, filename),
        {"kind": "metadata", "filename": filename},
    )
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.post("/api/thumbnails")
def start_thumbnail_cache_job():
    payload = request_data()
    filenames = payload.get("filenames")
    if not isinstance(filenames, list) or any(not isinstance(name, str) for name in filenames):
        return jsonify(error="Invalid file list."), 400
    filenames = list(dict.fromkeys(filenames))
    if len(filenames) > 1000:
        return jsonify(error="Too many files to load thumbnails at once."), 400
    args = operation_args(payload)
    initial = {
        "completed": 0,
        "total": len(filenames),
        "cooperative_cancel": True,
        "progress": {"percent": 0},
        "thumbnails": {name: {"status": "pending"} for name in filenames},
    }
    job_id, error = start_job(
        "Loading thumbnails",
        lambda current_job_id: cache_thumbnails(current_job_id, args, filenames),
        initial,
    )
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.get("/api/thumbnails/<cache_key>")
def get_cached_thumbnail(cache_key: str):
    if re.fullmatch(r"[a-f0-9]{64}", cache_key) is None:
        abort(404)
    path = THUMBNAIL_CACHE / f"{cache_key}.jpg"
    if not path.is_file():
        abort(404)
    try:
        return send_file(path, mimetype="image/jpeg", conditional=True, max_age=86400)
    except FileNotFoundError:
        abort(404)
