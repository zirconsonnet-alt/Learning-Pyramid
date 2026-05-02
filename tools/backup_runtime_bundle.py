from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.auth_store import AuthStore
from backend.system.data_safety_audit import append_data_safety_audit_event, new_data_safety_audit_event
from backend.system.sql_backend import create_persist_store, current_sql_runtime_config
from backend.system.version import APP_VERSION


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _media_payload_from_roots(media_roots: tuple[Path, ...]) -> tuple[dict[str, str], dict[str, str], int]:
    payload: dict[str, str] = {}
    checksums: dict[str, str] = {}
    total_bytes = 0
    for root in media_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rel = path.relative_to(root).as_posix()
            data = path.read_bytes()
            payload[rel] = base64.b64encode(data).decode("ascii")
            checksums[rel] = _sha256_bytes(data)
            total_bytes += len(data)
    return payload, checksums, total_bytes


def verify_runtime_bundle(input_path: Path) -> dict[str, object]:
    source = Path(input_path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    errors: list[str] = []
    manifest = payload.get("manifest")
    media_payload = payload.get("mediaPayload", {})
    if not isinstance(manifest, dict):
        errors.append("missing manifest")
    if not isinstance(media_payload, dict):
        errors.append("mediaPayload must be an object")
        media_payload = {}

    media = manifest.get("media", {}) if isinstance(manifest, dict) else {}
    checksums = media.get("checksums", {}) if isinstance(media, dict) else {}
    if isinstance(checksums, dict):
        for rel, expected in checksums.items():
            encoded = media_payload.get(rel)
            if not isinstance(encoded, str):
                errors.append(f"missing media payload: {rel}")
                continue
            try:
                data = base64.b64decode(encoded.encode("ascii"), validate=True)
            except Exception:
                errors.append(f"invalid media payload encoding: {rel}")
                continue
            if _sha256_bytes(data) != expected:
                errors.append(f"media checksum mismatch: {rel}")

    return {
        "state": "failed" if errors else "verified",
        "verifiedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "errors": errors,
        "warnings": [],
    }


def backup_runtime_bundle(
    *,
    output_path: Path,
    include_media: bool = False,
    media_roots: tuple[Path, ...] = tuple(),
    verify: bool = False,
    audit_path: Path | None = None,
) -> Path:
    cfg = current_sql_runtime_config()
    store = create_persist_store(legacy_root=REPO_ROOT)
    auth = AuthStore()
    media_payload: dict[str, str] = {}
    media_checksums: dict[str, str] = {}
    media_total_bytes = 0
    if include_media:
        media_payload, media_checksums, media_total_bytes = _media_payload_from_roots(tuple(Path(root) for root in media_roots))
    payload = {
        "metadata": {
            "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "appVersion": APP_VERSION,
            "sqlBackend": cfg.backend,
        },
        "manifest": {
            "schemaVersion": 2,
            "media": {
                "fileCount": len(media_payload),
                "totalBytes": media_total_bytes,
                "checksums": media_checksums,
            },
        },
        "storeSnapshot": store.load_snapshot(),
        "authSnapshot": auth.export_snapshot(),
        "mediaPayload": media_payload,
    }
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if verify:
        report = verify_runtime_bundle(target)
        if report["state"] != "verified":
            raise ValueError("; ".join(str(item) for item in report["errors"]))
    append_data_safety_audit_event(
        audit_path or (REPO_ROOT / "data" / "data-safety-audit.jsonl"),
        new_data_safety_audit_event(
            event_id=f"backup-{target.stem}",
            actor="operator",
            operation_type="backup",
            operation_id=target.name,
            result="ok",
            protected_classes=("auth-users", "project-store", "media-assets"),
            inputs_summary={"includeMedia": include_media, "mediaFileCount": len(media_payload)},
        ),
    )
    return target


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup the current LearningPyramid runtime state into a JSON bundle.")
    parser.add_argument("output", type=Path, help="Path to write the backup bundle JSON")
    parser.add_argument("--include-media", action="store_true", help="Include uploaded media files in the backup bundle")
    parser.add_argument("--media-root", action="append", type=Path, default=[], help="Media root to include; can be repeated")
    parser.add_argument("--verify", action="store_true", help="Verify the written backup bundle")
    parser.add_argument("--verify-only", action="store_true", help="Only verify an existing bundle")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        report = verify_runtime_bundle(Path(args.output))
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["state"] == "verified" else 1
    backup_runtime_bundle(output_path=Path(args.output), include_media=bool(args.include_media), media_roots=tuple(args.media_root), verify=bool(args.verify))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
