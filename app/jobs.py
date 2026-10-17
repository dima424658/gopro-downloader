"""Background job lifecycle, progress reporting, and cancellation."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify

from .notifications import notify_download_result

job_routes = Blueprint("jobs", __name__)
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
logger = logging.getLogger(__name__)


class TransferCancelled(Exception):
    """Raised by the streaming transfer when the user cancels a job."""


def _job_worker(job_id: str, label: str, operation: Callable[[str], Coroutine[Any, Any, Any]]) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(operation(job_id))
    with _jobs_lock:
        job = _jobs[job_id]
        job["_loop"] = loop
        job["_task"] = task
        cancel_requested = job["_cancel_event"].is_set()
    if cancel_requested and not job.get("cooperative_cancel"):
        task.cancel()
    try:
        result = loop.run_until_complete(task)
        if isinstance(result, dict):
            result = {key: str(value) for key, value in result.items()}
        elif isinstance(result, Path):
            result = str(result)
        with _jobs_lock:
            _jobs[job_id].update(done=True, result=result)
            completed_job = _jobs[job_id].copy()
        logger.info("Background job completed: %s (id=%s)", label, job_id)
        if completed_job.get("command") in {"download", "download-many"}:
            notify_download_result(
                success=True,
                filename=completed_job.get("filename"),
                filenames=completed_job.get("filenames") if completed_job.get("command") == "download-many" else None,
            )
    except (asyncio.CancelledError, TransferCancelled):
        with _jobs_lock:
            _jobs[job_id].update(done=True, cancelled=True)
        logger.info("Background job cancelled: %s (id=%s)", label, job_id)
    except Exception as exc:  # noqa: BLE001 - persist any operation failure for the UI.
        with _jobs_lock:
            if _jobs[job_id]["_cancel_event"].is_set():
                _jobs[job_id].update(done=True, cancelled=True)
                logger.info("Background job cancelled: %s (id=%s)", label, job_id)
            else:
                _jobs[job_id].update(done=True, error=str(exc))
                failed_job = _jobs[job_id].copy()
                logger.exception("Background job failed: %s (id=%s)", label, job_id)
                if failed_job.get("command") in {"download", "download-many"}:
                    progress = failed_job.get("progress") or {}
                    notify_download_result(
                        success=False,
                        filename=progress.get("filename") or failed_job.get("filename"),
                        error=str(exc),
                    )
    finally:
        with _jobs_lock:
            _jobs[job_id].pop("_loop", None)
            _jobs[job_id].pop("_task", None)
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
        asyncio.set_event_loop(None)


def start_job(
    label: str,
    operation: Callable[[str], Coroutine[Any, Any, Any]],
    initial: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    with _jobs_lock:
        if any(not job["done"] for job in _jobs.values()):
            return None, "Another operation is already running. Wait for it to finish."
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "label": label,
            "done": False,
            "progress": None,
            "cooperative_cancel": False,
            "_cancel_event": threading.Event(),
            **(initial or {}),
        }
    threading.Thread(
        target=_job_worker,
        args=(job_id, label, operation),
        name=f"gopro-job-{job_id[:8]}",
        daemon=True,
    ).start()
    return job_id, None


def publish_progress(job_id: str, progress: dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[job_id]["progress"] = progress


def get_cancel_event(job_id: str) -> threading.Event:
    with _jobs_lock:
        return _jobs[job_id]["_cancel_event"]


def set_thumbnail_progress(job_id: str, filename: str, value: dict[str, Any]) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job["thumbnails"][filename] = value
        job["completed"] = sum(item.get("status") != "pending" for item in job["thumbnails"].values())
        total = job.get("total", 0)
        if total:
            job["progress"] = {"filename": filename, "percent": int(job["completed"] * 100 / total)}


@job_routes.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify(error="Operation not found."), 404
        return jsonify({key: value for key, value in job.items() if not key.startswith("_")})


@job_routes.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify(error="Operation not found."), 404
        if job["done"]:
            return jsonify(error="Operation has already finished."), 409
        job["cancel_requested"] = True
        job["_cancel_event"].set()
        loop = job.get("_loop")
        task = job.get("_task")
        cooperative_cancel = job.get("cooperative_cancel", False)
    if loop is not None and task is not None and not cooperative_cancel:
        loop.call_soon_threadsafe(task.cancel)
    return jsonify(cancel_requested=True), 202
