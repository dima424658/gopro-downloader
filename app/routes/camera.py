"""Camera discovery, BLE connection, and Wi-Fi provisioning endpoints."""

from __future__ import annotations

import re
from typing import Any

from flask import Blueprint, jsonify

from ..cohn import connect_ble, provision, refresh_camera_battery, scan_ble_devices, scan_wifi_networks
from ..jobs import start_job
from ..settings import write_desktop_settings
from .helpers import operation_args, optional_text, request_data

blueprint = Blueprint("camera_api", __name__)


@blueprint.post("/api/provision")
def start_provision():
    payload = request_data()
    args = operation_args(payload)

    async def provision_and_store_ssid(_: str) -> Any:
        result = await provision(args)
        if args.ssid:
            write_desktop_settings({"wifi_ssid": args.ssid})
        return result

    job_id, error = start_job("Configure COHN", provision_and_store_ssid)
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.post("/api/ble/scan")
def start_ble_scan():
    job_id, error = start_job("Discover GoPro cameras over Bluetooth", lambda _: scan_ble_devices())
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.post("/api/ble/connect")
def start_ble_connection():
    payload = request_data()
    target = optional_text(payload, "target")
    if target and re.fullmatch(r"[A-Za-z0-9]{4}", target) is None:
        return jsonify(error="Enter the last four characters of the camera's serial number."), 400
    args = operation_args(payload)
    job_id, error = start_job(
        "Connect to GoPro over Bluetooth",
        lambda _: connect_ble(target, args.output_dir / "cohn_db.json"),
    )
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202


@blueprint.post("/api/camera/battery")
def get_camera_battery():
    args = operation_args(request_data())
    return jsonify(battery_percent=refresh_camera_battery(args.output_dir))


@blueprint.post("/api/wifi/scan")
def start_wifi_scan():
    payload = request_data()
    target = optional_text(payload, "target")
    if not target:
        return jsonify(error="Connect to the camera over Bluetooth first."), 400
    args = operation_args(payload)
    job_id, error = start_job(
        "Scan for Wi-Fi networks",
        lambda _: scan_wifi_networks(target, args.output_dir / "cohn_db.json"),
    )
    if error:
        return jsonify(error=error), 409
    return jsonify(job_id=job_id), 202
