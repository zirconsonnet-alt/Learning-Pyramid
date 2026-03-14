from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.system.runtime_env import resource_root
from backend.system.versioning import ComparableVersion, compare_versions


_ASSET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^LearningPyramidDesktopAgent-(?P<version>.+)-Setup\.exe$", "installer_exe"),
    (r"^LearningPyramidDesktopAgent-(?P<version>.+)-windows-installer\.zip$", "installer_zip"),
    (r"^LearningPyramidDesktopAgent-(?P<version>.+)-windows-standalone\.zip$", "standalone_zip"),
)
_RELEASE_MANIFEST_PATTERN = re.compile(r"^LearningPyramidDesktopAgent-(?P<version>.+)-release\.json$", re.IGNORECASE)
_ASSET_PREFERENCE = {
    "installer_exe": 0,
    "installer_zip": 1,
    "standalone_zip": 2,
}


def desktop_agent_release_root() -> Path:
    configured = str(os.getenv("PLM_DESKTOP_AGENT_RELEASE_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (resource_root() / "release").resolve()


def _sha256_text(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _utc_text_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()


def _release_require_signed() -> bool:
    return str(os.getenv("PLM_DESKTOP_AGENT_RELEASE_REQUIRE_SIGNED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _match_asset(path: Path) -> tuple[str, str] | None:
    for pattern, kind in _ASSET_PATTERNS:
        match = re.match(pattern, path.name, flags=re.IGNORECASE)
        if match is None:
            continue
        version = str(match.group("version") or "").strip()
        if not version:
            continue
        try:
            ComparableVersion(version)
        except ValueError:
            continue
        return version, kind
    return None


def _asset_dto(path: Path, *, version: str, kind: str) -> dict[str, Any]:
    asset_name = path.name
    return {
        "name": asset_name,
        "version": version,
        "kind": kind,
        "sizeBytes": int(path.stat().st_size),
        "sha256": _sha256_text(path),
        "integrityMode": "sha256",
        "publishedAt": _utc_text_from_timestamp(path.stat().st_mtime),
        "downloadPath": f"/api/system/desktop-agent-release/assets/{asset_name}",
        "signature": {
            "status": "UNKNOWN" if kind == "installer_exe" else "UNSUPPORTED",
            "subject": None,
            "issuer": None,
            "thumbprint": None,
            "signedAt": None,
            "source": "generated",
        },
        "silentInstall": {
            "supported": kind in {"installer_exe", "installer_zip"},
            "strategy": "inno_exe" if kind == "installer_exe" else ("powershell_zip" if kind == "installer_zip" else "unsupported"),
            "relaunch": kind in {"installer_exe", "installer_zip"},
        },
    }


def _load_release_manifests(root: Path) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    if not root.exists() or not root.is_dir():
        return manifests
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        match = _RELEASE_MANIFEST_PATTERN.match(path.name)
        if match is None:
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        version = str(raw.get("version") or match.group("version") or "").strip()
        if not version:
            continue
        assets = raw.get("assets")
        if not isinstance(assets, dict):
            raw["assets"] = {}
        manifests[version] = raw
    return manifests


def _merge_asset_manifest_metadata(asset: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return asset
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        return asset
    asset_meta = assets.get(str(asset["name"]))
    if not isinstance(asset_meta, dict):
        return asset
    merged = dict(asset)
    signature = asset_meta.get("signature")
    if isinstance(signature, dict):
        merged["signature"] = {
            "status": str(signature.get("status") or merged["signature"]["status"]).strip().upper(),
            "subject": None if signature.get("subject") is None else str(signature.get("subject")),
            "issuer": None if signature.get("issuer") is None else str(signature.get("issuer")),
            "thumbprint": None if signature.get("thumbprint") is None else str(signature.get("thumbprint")),
            "signedAt": None if signature.get("signedAt") is None else str(signature.get("signedAt")),
            "source": None if signature.get("source") is None else str(signature.get("source")),
        }
    silent_install = asset_meta.get("silentInstall")
    if isinstance(silent_install, dict):
        merged["silentInstall"] = {
            "supported": bool(silent_install.get("supported", merged["silentInstall"]["supported"])),
            "strategy": str(silent_install.get("strategy") or merged["silentInstall"]["strategy"]),
            "relaunch": bool(silent_install.get("relaunch", merged["silentInstall"]["relaunch"])),
        }
    release_notes = manifest.get("releaseNotes")
    if release_notes is not None:
        merged["releaseNotes"] = str(release_notes)
    return merged


def _signature_status(asset: dict[str, Any]) -> str:
    signature = asset.get("signature")
    if not isinstance(signature, dict):
        return ""
    return str(signature.get("status") or "").strip().upper()


def _apply_release_policy(assets: tuple[dict[str, Any], ...]) -> tuple[tuple[dict[str, Any], ...], int]:
    if not _release_require_signed():
        return assets, 0
    accepted: list[dict[str, Any]] = []
    rejected_count = 0
    for asset in assets:
        if _signature_status(asset) == "SIGNED":
            accepted.append(asset)
            continue
        rejected_count += 1
    return tuple(accepted), rejected_count


def _release_policy_dto(
    *,
    total_asset_count: int,
    visible_asset_count: int,
    rejected_asset_count: int,
) -> dict[str, Any]:
    require_signed = _release_require_signed()
    return {
        "requireSigned": require_signed,
        "acceptedSignatureStatuses": ["SIGNED"] if require_signed else [],
        "rejectedAssetCount": int(rejected_asset_count),
        "visibleAssetCount": int(visible_asset_count),
        "totalAssetCount": int(total_asset_count),
    }


def _list_desktop_agent_release_assets_raw() -> tuple[dict[str, Any], ...]:
    root = desktop_agent_release_root()
    if not root.exists() or not root.is_dir():
        return ()
    manifests = _load_release_manifests(root)
    items: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        matched = _match_asset(path)
        if matched is None:
            continue
        version, kind = matched
        items.append(_merge_asset_manifest_metadata(_asset_dto(path, version=version, kind=kind), manifests.get(version)))
    items.sort(
        key=lambda item: (
            ComparableVersion(str(item["version"])),
            -_ASSET_PREFERENCE.get(str(item["kind"]), 99),
            str(item["name"]),
        ),
        reverse=True,
    )
    return tuple(items)


def list_desktop_agent_release_assets() -> tuple[dict[str, Any], ...]:
    items, _ = _apply_release_policy(_list_desktop_agent_release_assets_raw())
    return items


def get_latest_desktop_agent_release(*, current_version: str | None = None) -> dict[str, Any]:
    raw_assets = _list_desktop_agent_release_assets_raw()
    assets, rejected_asset_count = _apply_release_policy(raw_assets)
    policy = _release_policy_dto(
        total_asset_count=len(raw_assets),
        visible_asset_count=len(assets),
        rejected_asset_count=rejected_asset_count,
    )
    if not assets:
        return {
            "available": False,
            "requestedVersion": None if current_version is None else str(current_version),
            "updateAvailable": False,
            "latest": None,
            "policy": policy,
        }

    latest_version = str(assets[0]["version"])
    latest_assets = [item for item in assets if str(item["version"]) == latest_version]
    latest_assets.sort(key=lambda item: (_ASSET_PREFERENCE.get(str(item["kind"]), 99), str(item["name"])))
    preferred_asset = latest_assets[0] if latest_assets else None
    published_at = max(str(item["publishedAt"]) for item in latest_assets)
    release_notes = next((str(item.get("releaseNotes")) for item in latest_assets if item.get("releaseNotes")), None)
    update_available = False
    if current_version:
        try:
            update_available = compare_versions(str(current_version), latest_version) < 0
        except ValueError:
            update_available = True
    return {
        "available": True,
        "requestedVersion": None if current_version is None else str(current_version),
        "updateAvailable": update_available,
        "latest": {
            "version": latest_version,
            "publishedAt": published_at,
            "assetCount": len(latest_assets),
            "preferredAsset": preferred_asset,
            "assets": latest_assets,
            "releaseNotes": release_notes,
        },
        "policy": policy,
    }


def resolve_desktop_agent_release_asset(filename: str) -> Path | None:
    if get_desktop_agent_release_asset_dto(filename) is None:
        return None
    root = desktop_agent_release_root()
    if not root.exists() or not root.is_dir():
        return None
    candidate = (root / Path(str(filename or "")).name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    matched = _match_asset(candidate)
    if matched is None:
        return None
    return candidate


def get_desktop_agent_release_asset_dto(filename: str) -> dict[str, Any] | None:
    normalized = Path(str(filename or "")).name
    for item in list_desktop_agent_release_assets():
        if str(item.get("name")) == normalized:
            return dict(item)
    return None
