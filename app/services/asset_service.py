from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import ASSET_DIR, BASE_DIR


SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

MANIFEST_KEYS = {
    "people": ("people",),
    "person": ("people",),
    "posters": ("posters", "movies", "films"),
    "poster": ("posters", "movies", "films"),
    "movies": ("posters", "movies", "films"),
    "organizations": ("organizations", "companies"),
    "organization": ("organizations", "companies"),
    "awards": ("awards",),
    "award": ("awards",),
}

PEOPLE_SUBDIRS = {
    "actor": "actors",
    "actors": "actors",
    "director": "directors",
    "directors": "directors",
    "critic": "critics",
    "critics": "critics",
}


def media_asset_path(kind: str, entity_id: str | None, subtype: str | None = None) -> str | None:
    resolved = resolve_media_asset(kind, entity_id, subtype=subtype)
    return str(resolved) if resolved else None


def resolve_media_asset(kind: str, entity_id: str | None, subtype: str | None = None) -> Path | None:
    normalized_id = str(entity_id or "").strip()
    if not normalized_id:
        return None

    normalized_kind = _normalize_kind(kind)
    for root, manifest in _manifest_sources():
        manifest_path = _manifest_lookup(manifest, normalized_kind, normalized_id)
        if manifest_path:
            resolved = _safe_existing_path(root, manifest_path)
            if resolved:
                return resolved

    for root in _media_roots():
        for directory in _fallback_directories(normalized_kind, subtype):
            for extension in SUPPORTED_IMAGE_EXTENSIONS:
                candidate = root / directory / f"{normalized_id}{extension}"
                if candidate.is_file():
                    return candidate.resolve()
    return None


def media_patch_status() -> dict[str, Any]:
    counts = {"people": 0, "posters": 0, "organizations": 0, "awards": 0}
    for root in _media_roots():
        for image in root.rglob("*"):
            if not image.is_file() or image.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            parts = image.relative_to(root).parts
            if not parts:
                continue
            if parts[0] == "people":
                counts["people"] += 1
            elif parts[0] == "posters":
                counts["posters"] += 1
            elif parts[:2] == ("logos", "organizations"):
                counts["organizations"] += 1
            elif parts[:2] == ("logos", "awards"):
                counts["awards"] += 1
    return {"roots": [str(root) for root in _media_roots()], "counts": counts}


def _normalize_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized in {"person", "people"}:
        return "people"
    if normalized in {"poster", "posters", "movie", "movies", "film", "films"}:
        return "posters"
    if normalized in {"organization", "organizations", "company", "companies"}:
        return "organizations"
    if normalized in {"award", "awards"}:
        return "awards"
    return normalized


def _manifest_lookup(manifest: dict[str, Any], kind: str, entity_id: str) -> str | None:
    for key in MANIFEST_KEYS.get(kind, (kind,)):
        section = manifest.get(key)
        if isinstance(section, dict) and isinstance(section.get(entity_id), str):
            return section[entity_id]
    return None


def _fallback_directories(kind: str, subtype: str | None) -> list[Path]:
    if kind == "people":
        subdir = PEOPLE_SUBDIRS.get(str(subtype or "").strip().lower())
        directories = []
        if subdir:
            directories.append(Path("people") / subdir)
        directories.extend([Path("people") / "actors", Path("people") / "directors", Path("people") / "critics", Path("people")])
        return _dedupe_paths(directories)
    if kind == "posters":
        return [Path("posters") / "historical", Path("posters") / "player", Path("posters")]
    if kind == "organizations":
        return [Path("logos") / "organizations", Path("logos")]
    if kind == "awards":
        return [Path("logos") / "awards", Path("logos")]
    return [Path(kind)]


def _safe_existing_path(root: Path, relative_path: str) -> Path | None:
    if Path(relative_path).is_absolute():
        return None
    resolved = (root / relative_path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    if resolved.is_file() and resolved.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        return resolved
    return None


@lru_cache(maxsize=1)
def _manifest_sources() -> tuple[tuple[Path, dict[str, Any]], ...]:
    sources: list[tuple[Path, dict[str, Any]]] = []
    for root in _media_roots():
        for name in ("manifest.local.json", "manifest.json"):
            path = root / name
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                sources.append((root, data))
    return tuple(sources)


@lru_cache(maxsize=1)
def _media_roots() -> tuple[Path, ...]:
    roots = [
        BASE_DIR / "assets" / "media",
        ASSET_DIR / "media",
    ]
    return tuple(_dedupe_paths([root.resolve() for root in roots]))


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped
