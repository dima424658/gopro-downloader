"""Human-readable formatting for GoPro media metadata."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from open_gopro.models import PhotoMetadata, VideoMetadata
from open_gopro.models.constants.settings import PhotoLens, VideoLens

MetadataFormatter = Callable[[Any], str | None]

_VIDEO_LENS_LABELS = {
    "WIDE": "Wide",
    "NARROW": "Narrow",
    "SUPERVIEW": "SuperView",
    "LINEAR": "Linear",
    "MAX_SUPERVIEW": "Max SuperView",
    "LINEAR_HORIZON_LEVELING": "Linear with Horizon Leveling",
    "HYPERVIEW": "HyperView",
    "LINEAR_HORIZON_LOCK": "Linear with Horizon Lock",
    "MAX_HYPERVIEW": "Max HyperView",
    "ULTRA_SUPERVIEW": "Ultra SuperView",
    "ULTRA_WIDE": "Ultra-wide",
    "ULTRA_LINEAR": "Ultra Linear",
    "ULTRA_HYPERVIEW": "Ultra HyperView",
}
_PHOTO_LENS_LABELS = {
    "WIDE_12_MP": "Wide (12 MP)",
    "LINEAR_12_MP": "Linear (12 MP)",
    "NUM_9MP_WIDE": "Wide (9 MP)",
    "NARROW": "Narrow",
    "WIDE_23_MP": "Wide (23 MP)",
    "LINEAR_23_MP": "Linear (23 MP)",
    "WIDE_27_MP": "Wide (27 MP)",
    "LINEAR_27_MP": "Linear (27 MP)",
    "NUM_9MP_LINEAR": "Linear (9 MP)",
    "NUM_13MP_LINEAR": "Linear (13 MP)",
    "NUM_13MP_WIDE": "Wide (13 MP)",
    "NUM_13MP_ULTRA_WIDE": "Ultra-wide (13 MP)",
    "ULTRA_WIDE_12_MP": "Ultra-wide (12 MP)",
    "NUM_13MP_ULTRA_LINEAR": "Ultra-wide Linear (13 MP)",
    "MAX_SUPERVIEW": "Max SuperView",
    "WIDE": "Wide",
    "LINEAR": "Linear",
}
_LENS_PROJECTION_LABELS = {
    "GPRO": "GoPro Native Projection",
    "EACO": "EAC — Equi-Angular Cubemap projection",
    "EAC": "EAC — Equi-Angular Cubemap projection",
}
_DETAIL_FIELDS = (
    ("Stabilization", "image_stabilization"),
    ("Rotation", "rotate"),
    ("Field of view", "field_of_view"),
    ("Lens configuration", "lens_config"),
    ("Lens projection", "lens_projection"),
    ("Highlight count", "hilight_count"),
    ("LRV size", "lrv_file_size"),
    ("Audio", "audio_option"),
)


def _format_bytes(raw: Any) -> str | None:
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return None
    if size < 0:
        return None

    value = float(size)
    formatted = f"{size} B"
    for unit in ("KB", "MB", "GB", "TB"):
        if value < 1024:
            break
        value /= 1024
        formatted = f"{value:.1f} {unit}"
    return f"{formatted} ({size:,} B)".replace(",", " ")


def _format_enabled(raw: Any) -> str | None:
    if raw is None:
        return None
    return {"1": "Yes", "0": "No"}.get(str(raw), str(raw))


def _format_content_type(metadata: Any, raw: Any, filename: str | None = None) -> str:
    enum_name = getattr(raw, "name", None)
    if enum_name:
        return str(enum_name).replace("_", " ").title()

    raw_text = str(raw).strip()
    if raw_text.isdigit():
        if isinstance(metadata, VideoMetadata) or any(
            hasattr(metadata, field) for field in ("duration", "frame_rate", "audio_option")
        ):
            return "Video"
        if isinstance(metadata, PhotoMetadata) or any(
            hasattr(metadata, field) for field in ("high_dynamic_range", "wide_dynamic_range")
        ):
            return "Photo"
        suffix = filename.rpartition(".")[2].lower() if filename else ""
        if suffix in {"mp4", "mov", "lrv"}:
            return "Video"
        if suffix in {"jpg", "jpeg", "heic"}:
            return "Photo"
    return raw_text


def _format_lens_configuration(metadata: Any, raw: Any) -> str:
    content_type = str(getattr(metadata, "content_type", "")).lower()
    is_video = (
        isinstance(metadata, VideoMetadata)
        or content_type.startswith("video")
        or any(hasattr(metadata, field) for field in ("duration", "frame_rate", "audio_option"))
    )
    is_photo = (
        isinstance(metadata, PhotoMetadata)
        or content_type.startswith("image")
        or any(hasattr(metadata, field) for field in ("high_dynamic_range", "wide_dynamic_range"))
    )
    enum_type = PhotoLens if is_photo and not is_video else VideoLens
    labels = _VIDEO_LENS_LABELS if enum_type is VideoLens else _PHOTO_LENS_LABELS
    raw_text = str(raw).strip()
    enum_name = getattr(raw, "name", "").upper()
    if not enum_name:
        try:
            enum_name = enum_type(int(raw_text)).name if enum_type else raw_text.upper()
        except (TypeError, ValueError):
            enum_name = raw_text.upper()
    return labels.get(enum_name, raw_text)


def _format_lens_projection(raw: Any) -> str:
    raw_text = str(raw).strip()
    projection_name = raw_text.upper()
    try:
        projection_name = VideoLens(int(raw_text)).name
    except (TypeError, ValueError):
        pass
    return _VIDEO_LENS_LABELS.get(
        projection_name,
        _LENS_PROJECTION_LABELS.get(projection_name, raw_text),
    )


def _format_creation_date(raw: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(raw)).astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(raw)


def _format_frame_rate(metadata: Any) -> str | None:
    try:
        frame_rate = float(metadata.frame_rate) / float(metadata.frame_rate_divisor)
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None
    return f"{frame_rate:.3f}".rstrip("0").rstrip(".") + " fps" if frame_rate else None


def _format_duration(raw: Any) -> str | None:
    try:
        seconds = max(0, int(float(raw)))
    except (TypeError, ValueError):
        return str(raw)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def format_metadata_rows(metadata: Any, filename: str | None = None) -> list[dict[str, str]]:
    """Convert SDK metadata fields into display-ready label/value rows."""
    rows: list[dict[str, str]] = []

    def add(label: str, raw: Any, formatter: MetadataFormatter | None = None) -> None:
        if raw is None or raw == "":
            return
        rendered = formatter(raw) if formatter else str(raw)
        if rendered:
            rows.append({"label": label, "value": rendered})

    add(
        "Type",
        getattr(metadata, "content_type", None),
        lambda raw: _format_content_type(metadata, raw, filename),
    )
    add("Size", getattr(metadata, "file_size", None), _format_bytes)
    add("Creation date", getattr(metadata, "creation_timestamp", None), _format_creation_date)

    width = getattr(metadata, "width", None)
    height = getattr(metadata, "height", None)
    add("Resolution", f"{width} × {height}" if width and height else None)
    add("Duration", getattr(metadata, "duration", None), _format_duration)
    add("Frame rate", _format_frame_rate(metadata))

    formatters: dict[str, MetadataFormatter] = {
        "image_stabilization": _format_enabled,
        "lens_config": lambda raw: _format_lens_configuration(metadata, raw),
        "lens_projection": _format_lens_projection,
        "lrv_file_size": _format_bytes,
    }
    for label, field in _DETAIL_FIELDS:
        add(label, getattr(metadata, field, None), formatters.get(field))
    return rows
