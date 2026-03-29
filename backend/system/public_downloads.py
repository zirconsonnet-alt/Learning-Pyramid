from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from backend.system.runtime_env import executable_dir, resource_root


PUBLIC_DOWNLOADS_ENV = "PLM_PUBLIC_DOWNLOADS_DIR"
PUBLIC_DOWNLOADS_CATALOG = "catalog.json"


def public_downloads_root() -> Path:
    configured = (os.getenv(PUBLIC_DOWNLOADS_ENV) or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    candidates = (
        executable_dir() / "public-downloads",
        resource_root() / "public-downloads",
        executable_dir() / "release" / "public-downloads",
        resource_root() / "release" / "public-downloads",
    )
    for candidate in candidates:
        if candidate.exists() or (candidate / PUBLIC_DOWNLOADS_CATALOG).exists():
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_public_download_asset(asset_path: str) -> Path | None:
    normalized = _normalize_asset_path(asset_path)
    if normalized is None:
        return None

    root = public_downloads_root()
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except Exception:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def list_public_downloads() -> dict[str, object]:
    root = public_downloads_root()
    catalog_path = root / PUBLIC_DOWNLOADS_CATALOG
    if not catalog_path.exists():
        return {"generatedAt": None, "items": []}

    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return {"generatedAt": None, "items": []}

    if not isinstance(payload, dict):
        return {"generatedAt": None, "items": []}

    generated_at = payload.get("generatedAt")
    generated_at_text = generated_at.strip() if isinstance(generated_at, str) else None

    items: list[dict[str, object]] = []
    raw_items = payload.get("items")
    if isinstance(raw_items, list):
        for raw in raw_items:
            normalized = _normalize_catalog_item(raw)
            if normalized is not None:
                items.append(normalized)

    return {
        "generatedAt": generated_at_text or None,
        "items": items,
    }


def _normalize_catalog_item(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None

    asset_path = _normalize_asset_path(str(raw.get("assetPath") or raw.get("fileName") or ""))
    if asset_path is None:
        return None

    file_path = resolve_public_download_asset(asset_path)
    if file_path is None:
        return None

    included_components = _normalize_string_list(raw.get("includedComponents"))
    requirements = _normalize_string_list(raw.get("requirements"))

    version = str(raw.get("version") or "").strip()
    platform = str(raw.get("platform") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    display_name = str(raw.get("displayName") or raw.get("label") or file_path.stem).strip() or file_path.stem
    published_at = str(raw.get("publishedAt") or "").strip() or None
    sha256 = str(raw.get("sha256") or "").strip() or None

    return {
        "id": str(raw.get("id") or file_path.stem).strip() or file_path.stem,
        "displayName": display_name,
        "version": version or None,
        "platform": platform or None,
        "summary": summary or None,
        "fileName": file_path.name,
        "assetPath": asset_path,
        "downloadPath": f"/downloads/{quote(asset_path, safe='/')}",
        "publishedAt": published_at,
        "sha256": sha256,
        "sizeBytes": int(file_path.stat().st_size),
        "recommended": bool(raw.get("recommended", False)),
        "includedComponents": included_components,
        "requirements": requirements,
    }


def _normalize_asset_path(asset_path: str) -> str | None:
    normalized = asset_path.strip().replace("\\", "/")
    if not normalized:
        return None

    pure_path = PurePosixPath(normalized)
    if pure_path.is_absolute():
        return None

    safe_parts: list[str] = []
    for part in pure_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            return None
        safe_parts.append(part)

    if not safe_parts:
        return None
    return "/".join(safe_parts)


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result
