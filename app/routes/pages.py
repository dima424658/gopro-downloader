"""HTML pages and preference endpoints."""

from __future__ import annotations

import threading

from flask import Blueprint, jsonify, render_template, request

from ..settings import has_saved_cohn, read_desktop_settings, write_desktop_settings
from .helpers import request_data

blueprint = Blueprint("pages", __name__)
_media_refresh_lock = threading.Lock()
_media_refresh_version = 0


@blueprint.get("/")
def index():
    settings = read_desktop_settings()
    return render_template(
        "index.html",
        auto_refresh=has_saved_cohn(),
        cohn_dir=settings["cohn_dir"],
        media_dir=settings["media_dir"],
        theme=settings["theme"],
    )


@blueprint.get("/connect")
def connect_page():
    settings = read_desktop_settings()
    return render_template(
        "connect.html",
        media_dir=settings["media_dir"],
        cohn_dir=settings["cohn_dir"],
        wifi_ssid=settings["wifi_ssid"],
        theme=settings["theme"],
    )


@blueprint.post("/api/settings")
def update_desktop_settings():
    payload = request_data()
    try:
        settings = write_desktop_settings(payload)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(settings=settings)


@blueprint.route("/api/media/refresh-signal", methods=["GET", "POST"])
def media_refresh_signal():
    global _media_refresh_version
    with _media_refresh_lock:
        if request.method == "POST":
            _media_refresh_version += 1
        return jsonify(version=_media_refresh_version)
