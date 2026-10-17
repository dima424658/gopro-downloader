"""Thumbnail caching for camera media."""

from __future__ import annotations

import hashlib

from open_gopro import WirelessGoPro

from .cohn import OperationArgs, resolve_cohn_target
from .config_paths import THUMBNAIL_CACHE_PATH
from .jobs import (
    TransferCancelled,
    get_cancel_event,
    set_thumbnail_progress,
)
from .transfers import install_progress_stream

THUMBNAIL_CACHE = THUMBNAIL_CACHE_PATH


def thumbnail_key(target: str, filename: str) -> str:
    return hashlib.sha256(f"{target}:{filename}".encode()).hexdigest()


async def cache_thumbnails(job_id: str, args: OperationArgs, filenames: list[str]) -> None:
    target = resolve_cohn_target(args.target, args.output_dir / "cohn_db.json")
    cancel_signal = get_cancel_event(job_id)
    THUMBNAIL_CACHE.mkdir(parents=True, exist_ok=True)
    async with WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=args.output_dir / "cohn_db.json",
    ) as camera:
        for index, filename in enumerate(filenames):
            if cancel_signal.is_set():
                raise TransferCancelled()
            key = thumbnail_key(target, filename)
            cached_file = THUMBNAIL_CACHE / f"{key}.jpg"
            partial_file = THUMBNAIL_CACHE / f"{key}.part"
            url = f"/api/thumbnails/{key}"
            if cached_file.is_file():
                set_thumbnail_progress(job_id, filename, {"status": "ready", "url": url})
                continue
            try:
                install_progress_stream(
                    camera,
                    job_id,
                    cancel_signal,
                    filename,
                    lambda percent, _downloaded, _total, base=index: int(
                        (base + (percent or 0) / 100) * 100 / max(len(filenames), 1)
                    ),
                )
                response = await camera.http_command.get_thumbnail(
                    camera_file=filename,
                    local_file=partial_file,
                )
                if not response.ok or not partial_file.is_file():
                    raise RuntimeError(str(response))
                partial_file.replace(cached_file)
                set_thumbnail_progress(job_id, filename, {"status": "ready", "url": url})
            except TransferCancelled:
                partial_file.unlink(missing_ok=True)
                raise
            except Exception as exc:  # noqa: BLE001 - one failed thumbnail must not stop the batch.
                partial_file.unlink(missing_ok=True)
                set_thumbnail_progress(job_id, filename, {"status": "error", "error": str(exc)})
