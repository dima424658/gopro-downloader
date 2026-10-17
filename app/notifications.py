"""Native desktop notifications for completed media downloads."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def notify_download_result(
    *,
    success: bool,
    filename: str | None = None,
    filenames: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Show a cross-platform system notification without affecting the job result."""
    try:
        from desktop_notifier.sync import DesktopNotifierSync
    except ImportError:
        logger.warning("Desktop notifications unavailable; install dependencies from requirements.txt")
        return

    if success and filenames is not None:
        title = "Downloads complete"
        message = f"Downloaded {len(filenames)} files."
    elif success:
        title = "Download complete"
        message = f"Downloaded {Path(filename or 'file').name}."
    else:
        title = "Download failed"
        subject = Path(filename).name if filename else "The download could not be completed."
        detail = " ".join((error or "").split())
        message = f"{subject}: {detail}" if detail else subject

    try:
        DesktopNotifierSync(app_name="GoPro Downloader").send(title=title, message=message[:240])
    except Exception:  # noqa: BLE001 - notification errors must not break download jobs.
        logger.exception("Could not show a download notification")
