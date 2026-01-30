
"""
media_normalizer.py

C.24.4.11 – Media Normalization (OBJE First-Class)

- Operates on modern export JSON dicts
- Normalizes MediaObjectEntity blocks under root["media_objects"]
- Never deletes or mutates original fields
- Adds a safe, additive `normalized_media` block
- Idempotent and filesystem-independent
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from gedcom_parser.logger import get_logger

log = get_logger("media_normalizer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"}
_VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "wmv"}
_AUDIO_EXTS = {"mp3", "wav", "aac", "ogg", "flac"}
_DOC_EXTS = {"pdf", "txt", "doc", "docx", "rtf"}


def _clean_str(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    return " ".join(str(v).strip().split()) or None


def _split_path(path: str) -> Tuple[str, Optional[str]]:
    """
    Return (normalized_path, extension)
    """
    norm = path.replace("\\", "/").strip()
    base = os.path.basename(norm)
    if "." in base:
        ext = base.rsplit(".", 1)[-1].lower()
    else:
        ext = None
    return norm, ext


def _classify_extension(ext: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Return (media_kind, guessed_mime)
    """
    if not ext:
        return ("unknown", None)

    if ext in _IMAGE_EXTS:
        return ("image", f"image/{'jpeg' if ext in {'jpg', 'jpeg'} else ext}")
    if ext in _VIDEO_EXTS:
        return ("video", f"video/{ext}")
    if ext in _AUDIO_EXTS:
        return ("audio", f"audio/{ext}")
    if ext in _DOC_EXTS:
        return ("document", f"application/{ext}")

    return ("unknown", None)


# ---------------------------------------------------------------------------
# Core normalization
# ---------------------------------------------------------------------------

def normalize_media_objects(root: Dict[str, Any]) -> Dict[str, int]:
    """
    Mutates root in-place (additive only).

    Returns counters for logging / verification.
    """
    counts = {
        "media_objects": 0,
        "files_seen": 0,
        "normalized_added": 0,
        "skipped_existing": 0,
    }

    media_objects = root.get("media_objects", {})
    if not isinstance(media_objects, dict):
        return counts

    for key, media in media_objects.items():
        if not isinstance(media, dict):
            continue

        counts["media_objects"] += 1

        # Idempotency: do not overwrite existing normalization
        if "normalized_media" in media:
            counts["skipped_existing"] += 1
            continue

        files = media.get("files") or []
        if not isinstance(files, list) or not files:
            # Still add a minimal normalized block
            media["normalized_media"] = {
                "file_count": 0,
                "media_kind": "unknown",
            }
            counts["normalized_added"] += 1
            continue

        counts["files_seen"] += len(files)

        # Use first file as primary (non-destructive heuristic)
        primary = files[0]
        path = _clean_str(primary.get("path")) if isinstance(primary, dict) else None

        norm_path = None
        ext = None
        media_kind = "unknown"
        guessed_mime = None

        if path:
            norm_path, ext = _split_path(path)
            media_kind, guessed_mime = _classify_extension(ext)

        media["normalized_media"] = {
            "file_count": len(files),
            "primary_path": path,
            "normalized_path": norm_path,
            "extension": ext,
            "media_kind": media_kind,
            "guessed_mime": guessed_mime,
        }

        counts["normalized_added"] += 1

    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="C.24.4.11 – Media normalization (OBJE first-class)"
    )
    ap.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input JSON (export_xref.json or later)",
    )
    ap.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output JSON with normalized media objects",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = ap.parse_args(argv)

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    counts = normalize_media_objects(root)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)

    log.info(
        "Media normalization complete: media_objects=%d files_seen=%d "
        "normalized_added=%d skipped_existing=%d",
        counts["media_objects"],
        counts["files_seen"],
        counts["normalized_added"],
        counts["skipped_existing"],
    )

    print(f"[INFO] Media normalization written to: {args.output}")


if __name__ == "__main__":
    main()
