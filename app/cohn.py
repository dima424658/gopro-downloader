"""Shared GoPro COHN operations used by the desktop application."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from bleak import BleakScanner
from open_gopro import WirelessGoPro
from open_gopro.domain.exceptions import GoProError
from returns.pipeline import is_successful

from .camera_status import battery_percent_from_state, get_battery_percent, set_battery_percent

logger = logging.getLogger(__name__)
_GOPRO_NAME = re.compile(r"^GoPro ([A-Z0-9]{4})$")
BLE_ATTEMPT_TIMEOUT = 5
BLE_TOTAL_TIMEOUT = 18
BLE_RETRIES = 2


@dataclass(slots=True)
class OperationArgs:
    target: str | None
    ssid: str | None
    wifi_password: str | None
    output_dir: Path
    media_dir: Path


def save_private_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows does not support POSIX mode bits; the files are still excluded
        # from version control by .gitignore.
        pass


def checked_filename(filename: str | None) -> str:
    """Keep camera paths within the media root and return the API filename."""
    if not isinstance(filename, str) or not filename:
        raise ValueError("No filename specified")
    normalized = filename.replace("\\", "/")
    if normalized.startswith("/") or any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ValueError("Invalid file path")
    return normalized


def resolve_cohn_target(target: str | None, database_path: Path) -> str:
    """Get the COHN camera identifier from an explicit target or saved DB entry."""
    if target:
        return target
    try:
        database = json.loads(database_path.read_text(encoding="utf-8"))
        serials = {
            record["serial"]
            for table in database.values()
            if isinstance(table, dict)
            for record in table.values()
            if isinstance(record, dict) and record.get("serial")
        }
    except (OSError, json.JSONDecodeError):
        serials = set()

    if len(serials) == 1:
        return serials.pop()
    if not serials:
        raise ValueError(
            f"No COHN camera entry exists in {database_path}. Configure COHN first "
            "or enter the last four characters of the serial number."
        )
    raise ValueError(
        "The COHN database contains multiple cameras; specify one using the last four characters of its serial number."
    )


async def media_operation(args: OperationArgs) -> list[str]:
    """Return the camera's media filenames over its authenticated COHN interface."""
    database_path = args.output_dir / "cohn_db.json"
    async with WirelessGoPro(
        target=resolve_cohn_target(args.target, database_path),
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=database_path,
    ) as camera:
        response = await camera.http_command.get_media_list()
        if not response.ok:
            raise RuntimeError(f"Could not retrieve the media list: {response}")
        return [item.filename for item in response.data.files]


async def _read_camera_battery(output_dir: Path) -> int | None:
    """Read battery percentage through the SDK's authenticated COHN connection."""
    database_path = output_dir / "cohn_db.json"
    async with WirelessGoPro(
        target=resolve_cohn_target(None, database_path),
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=database_path,
    ) as camera:
        response = await camera.http_command.get_camera_state()
        if not response.ok or not isinstance(response.data, dict):
            return None
        return battery_percent_from_state(response.data)


def refresh_camera_battery(output_dir: Path) -> int | None:
    """Read the latest battery percentage from the authenticated COHN state endpoint."""
    try:
        battery_percent = asyncio.run(_read_camera_battery(output_dir))
        if battery_percent is not None:
            set_battery_percent(battery_percent)
            return battery_percent
    except (GoProError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        logger.debug("Could not refresh camera battery status: %s", exc)
    return get_battery_percent()


async def scan_ble_devices() -> list[dict[str, str]]:
    """Discover nearby GoPro BLE advertisements using the SDK's device naming convention."""
    devices: dict[str, dict[str, str]] = {}

    def on_advertisement(device, advertisement) -> None:
        name = advertisement.local_name or device.name or ""
        match = _GOPRO_NAME.fullmatch(name)
        if match:
            devices[match.group(1)] = {"target": match.group(1), "name": name}

    async with BleakScanner(detection_callback=on_advertisement):
        await asyncio.sleep(6)
    return list(devices.values())


@asynccontextmanager
async def _open_ble_camera(target: str | None, database_path: Path) -> AsyncGenerator[WirelessGoPro, None]:
    """Open a BLE-only camera with a short per-attempt and overall timeout."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    camera = WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.BLE},
        cohn_db=database_path,
    )
    try:
        try:
            await asyncio.wait_for(
                camera.open(timeout=BLE_ATTEMPT_TIMEOUT, retries=BLE_RETRIES),
                timeout=BLE_TOTAL_TIMEOUT,
            )
        except TimeoutError as exc:
            raise TimeoutError(
                f"Could not connect to the camera over Bluetooth within {BLE_TOTAL_TIMEOUT} seconds. "
                "Make sure the camera is on and in pairing mode."
            ) from exc
        yield camera
    finally:
        await camera.close()


async def connect_ble(target: str | None, database_path: Path) -> str:
    """Verify that a GoPro can be fully opened over BLE and return its SDK identifier."""
    async with _open_ble_camera(target, database_path) as camera:
        identifier = camera.identifier
        logger.info("Bluetooth connection established with GoPro %s", identifier)
        return identifier


async def scan_wifi_networks(target: str | None, database_path: Path) -> list[str]:
    """Ask the camera to scan nearby Wi-Fi networks over BLE and return their SSIDs."""
    async with _open_ble_camera(target, database_path) as camera:
        result = await camera.access_point.scan_wifi_networks(timeout=30)
        if not is_successful(result):
            raise RuntimeError(f"Could not retrieve the Wi-Fi network list: {result.failure()}")
        entries = result.unwrap().entries
        return sorted({entry.ssid for entry in entries if entry.ssid})


def https_probe(url: str, ca_file: Path, username: str, password: str) -> None:
    """Issue an authenticated HTTPS GET using the GoPro's COHN root CA."""
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {token}"},
        method="GET",
    )
    context = ssl.create_default_context(cafile=str(ca_file))
    # Match Open GoPro's requests session: Python 3.13 enables these stricter
    # X.509 flags by default, which reject the camera-issued COHN CA certificate.
    context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    try:
        with urllib.request.urlopen(request, context=context, timeout=15) as response:
            logger.info("HTTPS check returned HTTP %s: %s", response.status, url)
    except urllib.error.HTTPError as exc:
        # A valid TLS connection can still get a route-specific HTTP error.
        logger.info("HTTPS and the certificate are working; the endpoint returned HTTP %s: %s", exc.code, url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Could not verify HTTPS: %s", exc)


async def provision(args: OperationArgs) -> dict[str, str | Path]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    database_path = args.output_dir / "cohn_db.json"
    async with _open_ble_camera(args.target, database_path) as camera:
        logger.info("Connected to GoPro %s over BLE", camera.identifier)

        credentials = camera.cohn.credentials
        wifi_needed = credentials is None or not credentials.is_complete or args.ssid is not None
        if wifi_needed:
            if not args.ssid:
                raise ValueError("Specify an SSID to configure Wi-Fi")
            wifi_result = await camera.access_point.connect(args.ssid, args.wifi_password or "")
            if not is_successful(wifi_result):
                raise RuntimeError(f"Could not connect GoPro to Wi-Fi: {wifi_result.failure()}")
        else:
            logger.info("Skipping Wi-Fi setup: existing COHN credentials were found")

        cohn_result = await camera.cohn.configure(force_reprovision=False)
        if not is_successful(cohn_result):
            raise RuntimeError(f"Could not configure COHN: {cohn_result.failure()}")

        credentials = camera.cohn.credentials
        if credentials is None or not credentials.is_complete:
            raise RuntimeError("The SDK did not save complete COHN credentials")

        ip_address = credentials.ip_address
        username = credentials.username
        auth_password = credentials.password
        certificate = credentials.certificate

    cert_path = args.output_dir / "gopro_cohn_ca.crt"
    credentials_path = args.output_dir / "gopro_cohn_credentials.json"
    save_private_text(cert_path, certificate)
    save_private_text(
        credentials_path,
        json.dumps(
            {
                "ip_address": ip_address,
                "username": username,
                "password": auth_password,
                "certificate": str(cert_path),
            },
            indent=2,
        )
        + "\n",
    )

    logger.info("COHN configured; camera is available at https://%s/", ip_address)
    logger.info("CA certificate saved: %s", cert_path)
    logger.info("Basic Auth credentials saved to a protected file: %s", credentials_path)
    logger.info("The camera and client must be connected to the same Wi-Fi network")

    https_probe(
        f"https://{ip_address}/gopro/camera/keep_alive",
        cert_path,
        username,
        auth_password,
    )
    return {"ip_address": ip_address, "certificate": cert_path, "credentials": credentials_path}
