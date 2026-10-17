"""HTTP streaming adapters for cancellable media transfers."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from open_gopro import WirelessGoPro
from open_gopro.models import GoProResp
from open_gopro.models.constants import ErrorCode

from .jobs import TransferCancelled, publish_progress

logger = logging.getLogger(__name__)
KEEP_ALIVE_INTERVAL_SECONDS = 3
KEEP_ALIVE_TIMEOUT_SECONDS = 2


def _keep_alive_url(base_url: str) -> str:
    """Build the camera's HTTP keep-alive URL from its current COHN address."""
    parsed = urlsplit(base_url)
    if not parsed.hostname:
        raise ValueError(f"Invalid GoPro base URL: {base_url!r}")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"http://{host}:8080/gopro/camera/keep_alive"


def _send_keep_alive(url: str) -> None:
    with urlopen(Request(url, method="GET"), timeout=KEEP_ALIVE_TIMEOUT_SECONDS) as response:
        if not 200 <= response.status < 300:
            raise OSError(f"GoPro keep-alive returned HTTP {response.status}")


async def _keep_camera_awake(url: str) -> None:
    """Periodically call Open GoPro's HTTP keep-alive endpoint during a transfer."""
    warned = False
    while True:
        try:
            await asyncio.to_thread(_send_keep_alive, url)
        except (OSError, URLError, TimeoutError) as exc:
            if not warned:
                logger.warning("GoPro HTTP keep-alive is unavailable at %s: %s", url, exc)
                warned = True
        await asyncio.sleep(KEEP_ALIVE_INTERVAL_SECONDS)


def install_progress_stream(
    camera: WirelessGoPro,
    job_id: str,
    cancel_event: threading.Event,
    filename: str,
    progress_mapper: Callable[[int | None, int, int | None], int | None],
    progress_context: dict[str, Any] | None = None,
) -> None:
    """Wrap the SDK binary stream to report byte progress and cooperatively cancel."""

    async def tracked_stream(message: Any, *, timeout: int = 15, rules: Any = None, **kwargs: Any) -> GoProResp:
        message = camera._handle_cohn(message)
        url = camera._base_url + message.build_url(path=kwargs["camera_file"])
        local_file = Path(kwargs["local_file"])

        def receive() -> Path:
            downloaded = 0
            total: int | None = None
            transfer_started = time.perf_counter()
            last_rate_sample = transfer_started
            last_rate_bytes = 0
            if cancel_event.is_set():
                raise TransferCancelled()
            publish_progress(
                job_id,
                {
                    "filename": filename,
                    "percent": progress_mapper(0, 0, None),
                    "downloaded": 0,
                    "total": None,
                    **(progress_context or {}),
                },
            )
            try:
                with camera._requests_session.get(
                    url,
                    stream=True,
                    timeout=timeout,
                    **camera._build_http_request_args(message),
                ) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("Content-Length")
                    total = int(content_length) if content_length and content_length.isdigit() else None
                    with local_file.open("wb") as output:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            if cancel_event.is_set():
                                raise TransferCancelled()
                            if not chunk:
                                continue
                            output.write(chunk)
                            downloaded += len(chunk)
                            now = time.perf_counter()
                            sample_duration = now - last_rate_sample
                            if sample_duration >= 0.5:
                                bytes_per_second = int((downloaded - last_rate_bytes) / sample_duration)
                                last_rate_sample = now
                                last_rate_bytes = downloaded
                            else:
                                bytes_per_second = int(downloaded / max(now - transfer_started, 0.001))
                            percent = progress_mapper(
                                min(99, int(downloaded * 100 / total)) if total else None,
                                downloaded,
                                total,
                            )
                            publish_progress(
                                job_id,
                                {
                                    "filename": filename,
                                    "percent": percent,
                                    "downloaded": downloaded,
                                    "total": total,
                                    "bytes_per_second": bytes_per_second,
                                    **(progress_context or {}),
                                },
                            )
                if total is not None and downloaded != total:
                    raise OSError(f"Download interrupted: received {downloaded} of {total} bytes.")
                publish_progress(
                    job_id,
                    {
                        "filename": filename,
                        "percent": progress_mapper(100, downloaded, total),
                        "downloaded": downloaded,
                        "total": total,
                        "bytes_per_second": int(downloaded / max(time.perf_counter() - transfer_started, 0.001)),
                        **(progress_context or {}),
                    },
                )
                return local_file
            except BaseException:
                local_file.unlink(missing_ok=True)
                raise

        keep_alive_task = asyncio.create_task(_keep_camera_awake(_keep_alive_url(camera._base_url)))
        try:
            result_path = await asyncio.to_thread(receive)
        finally:
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass
        return GoProResp(
            protocol=GoProResp.Protocol.HTTP,
            status=ErrorCode.SUCCESS,
            data=result_path,
            identifier=url,
        )

    camera._get_stream = tracked_stream
