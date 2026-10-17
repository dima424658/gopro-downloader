"""Camera media downloads and metadata retrieval."""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from open_gopro import WirelessGoPro

from .cohn import OperationArgs, checked_filename, resolve_cohn_target
from .jobs import (
    TransferCancelled,
    get_cancel_event,
    publish_progress,
)
from .metadata import format_metadata_rows
from .thumbnails import THUMBNAIL_CACHE, thumbnail_key
from .transfers import install_progress_stream

logger = logging.getLogger(__name__)


async def download_media(job_id: str, args: OperationArgs, command: str, filename: str | None) -> Path:
    if command == "download":
        return await _download_media_with_progress(
            job_id,
            args,
            checked_filename(filename),
            lambda percent, _downloaded, _total: percent,
            {},
        )

    requested = checked_filename(filename)
    target = resolve_cohn_target(args.target, args.output_dir / "cohn_db.json")
    args.media_dir.mkdir(parents=True, exist_ok=True)
    camera_name = Path(requested).name
    destination = args.media_dir / f"{camera_name}.thumbnail.jpg"
    partial = destination.with_name(destination.name + ".part")
    cancel_signal = get_cancel_event(job_id)

    async with WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=args.output_dir / "cohn_db.json",
    ) as camera:
        media_response = await camera.http_command.get_media_list()
        if not media_response.ok:
            raise RuntimeError(f"Could not retrieve the media list: {media_response}")
        if cancel_signal.is_set():
            raise TransferCancelled()
        if requested not in {item.filename for item in media_response.data.files}:
            raise ValueError(f"File {requested!r} was not found on the camera.")

        if command == "thumbnail":
            cached_file = THUMBNAIL_CACHE / f"{thumbnail_key(target, requested)}.jpg"
            if cached_file.is_file():
                shutil.copyfile(cached_file, destination)
                publish_progress(
                    job_id,
                    {
                        "filename": requested,
                        "percent": 100,
                        "downloaded": destination.stat().st_size,
                        "total": destination.stat().st_size,
                    },
                )
                return destination

        install_progress_stream(
            camera,
            job_id,
            cancel_signal,
            requested,
            lambda pct, _downloaded, _total: pct,
        )
        try:
            response = await camera.http_command.get_thumbnail(camera_file=requested, local_file=partial)
            if not response.ok or not partial.is_file():
                raise RuntimeError(f"Could not download {requested}: {response}")
            partial.replace(destination)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    logger.info("Media file saved: %s", destination)
    return destination


async def download_media_batch(job_id: str, args: OperationArgs, filenames: list[str]) -> None:
    """Download selected camera files one by one and report overall progress."""
    requested_files = list(dict.fromkeys(checked_filename(filename) for filename in filenames))
    if not requested_files:
        raise ValueError("Select at least one file to download.")

    cancel_signal = get_cancel_event(job_id)
    total = len(requested_files)
    completed_files: list[str] = []
    for index, filename in enumerate(requested_files):
        if cancel_signal.is_set():
            raise TransferCancelled()

        message = f"File {index + 1} of {total}: {Path(filename).name}"
        publish_progress(
            job_id,
            {
                "filename": filename,
                "percent": int(index * 100 / total),
                "message": message,
                "completed_files": completed_files.copy(),
            },
        )

        def map_progress(
            percent: int | None,
            _downloaded: int,
            _total: int | None,
            current_index: int = index,
        ) -> int | None:
            if percent is None:
                return int(current_index * 100 / total)
            return min(99, int((current_index + percent / 100) * 100 / total))

        await _download_media_with_progress(
            job_id,
            args,
            filename,
            map_progress,
            {
                "message": message,
                "filename": filename,
                "completed_files": completed_files.copy(),
            },
        )
        completed_files.append(filename)
        publish_progress(
            job_id,
            {
                "percent": int((index + 1) * 100 / total),
                "message": f"Downloaded {index + 1} of {total}: {Path(filename).name}",
                "completed_files": completed_files.copy(),
            },
        )
    publish_progress(
        job_id,
        {
            "percent": 100,
            "message": f"Downloaded {total} files",
            "completed_files": completed_files.copy(),
        },
    )


async def _download_media_with_progress(
    job_id: str,
    args: OperationArgs,
    filename: str,
    progress_mapper: Callable[[int | None, int, int | None], int | None],
    progress_context: dict[str, Any],
) -> Path:
    """Download one original with custom progress mapping for batch jobs."""
    requested = checked_filename(filename)
    target = resolve_cohn_target(args.target, args.output_dir / "cohn_db.json")
    args.media_dir.mkdir(parents=True, exist_ok=True)
    destination = args.media_dir / Path(requested).name
    partial = destination.with_name(destination.name + ".part")
    cancel_signal = get_cancel_event(job_id)

    async with WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=args.output_dir / "cohn_db.json",
    ) as camera:
        media_response = await camera.http_command.get_media_list()
        if not media_response.ok:
            raise RuntimeError(f"Could not retrieve the media list: {media_response}")
        if cancel_signal.is_set():
            raise TransferCancelled()
        if requested not in {item.filename for item in media_response.data.files}:
            raise ValueError(f"File {requested!r} was not found on the camera.")

        install_progress_stream(
            camera,
            job_id,
            cancel_signal,
            requested,
            progress_mapper,
            progress_context,
        )
        try:
            response = await camera.http_command.download_file(camera_file=requested, local_file=partial)
            if not response.ok or not partial.is_file():
                raise RuntimeError(f"Could not download {requested}: {response}")
            partial.replace(destination)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    logger.info("Media file saved: %s", destination)
    return destination


async def delete_camera_media(args: OperationArgs, filename: str | None) -> None:
    """Delete one camera file after confirming it is still present."""
    requested = checked_filename(filename)
    target = resolve_cohn_target(args.target, args.output_dir / "cohn_db.json")
    async with WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=args.output_dir / "cohn_db.json",
    ) as camera:
        media_response = await camera.http_command.get_media_list()
        if not media_response.ok:
            raise RuntimeError(f"Could not retrieve the media list: {media_response}")
        if requested not in {item.filename for item in media_response.data.files}:
            raise ValueError(f"File {requested!r} was not found on the camera.")

        response = await camera.http_command.delete_file(path=requested)
        if not response.ok:
            raise RuntimeError(f"Camera rejected  delete for {requested} with path {requested!r}")

        await asyncio.sleep(0.5)

        verification = await camera.http_command.get_media_list()
        if not verification.ok:
            raise RuntimeError(f"Could not verify deletion of {requested}: {verification}")
        if requested not in {item.filename for item in verification.data.files}:
            logger.info("Camera media file deleted: %s", requested)
            return

        raise RuntimeError(f"Camera still lists {requested!r} after delete", requested)


async def get_media_metadata(args: OperationArgs, filename: str | None) -> list[dict[str, str]]:
    requested = checked_filename(filename)
    target = resolve_cohn_target(args.target, args.output_dir / "cohn_db.json")
    async with WirelessGoPro(
        target=target,
        interfaces={WirelessGoPro.Interface.COHN},
        maintain_state=False,
        cohn_db=args.output_dir / "cohn_db.json",
    ) as camera:
        response = await camera.http_command.get_media_metadata(path=requested)
        if not response.ok:
            raise RuntimeError(f"Could not retrieve information for {requested}: {response}")
        return format_metadata_rows(response.data, requested)
