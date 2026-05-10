import argparse
import base64
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.auth_store import AuthStore
from backend.system.data_safety import collect_data_safety_status
from backend.system.data_safety_audit import append_data_safety_audit_event, new_data_safety_audit_event
from backend.system.sql_backend import create_persist_store
from tools.backup_runtime_bundle import verify_runtime_bundle


def _restore_media_payload(payload: dict, target_media_root: Path) -> int:
    media_payload = payload.get("mediaPayload", {})
    if not isinstance(media_payload, dict):
        raise ValueError("mediaPayload must be a JSON object")
    restored = 0
    for rel, encoded in media_payload.items():
        if not isinstance(rel, str) or not isinstance(encoded, str):
            raise ValueError("mediaPayload entries must be string to string")
        target = target_media_root / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(encoded.encode("ascii"), validate=True))
        restored += 1
    return restored


def restore_runtime_bundle(
    *,
    input_path: Path,
    dry_run: bool = False,
    confirm_replace: bool = False,
    target_media_root: Path | None = None,
    restore_runtime_data: bool = True,
    audit_path: Path | None = None,
) -> dict[str, object]:
    source = Path(input_path).expanduser().resolve()
    verification = verify_runtime_bundle(source)
    if verification["state"] != "verified":
        raise ValueError("Backup bundle is not verified: " + "; ".join(str(item) for item in verification["errors"]))
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup bundle must be a JSON object")

    store_snapshot = payload.get("storeSnapshot")
    auth_snapshot = payload.get("authSnapshot")
    if store_snapshot is not None and not isinstance(store_snapshot, dict):
        raise ValueError("storeSnapshot must be a JSON object or null")
    if auth_snapshot is None or not isinstance(auth_snapshot, dict):
        raise ValueError("authSnapshot must be a JSON object")

    media_payload = payload.get("mediaPayload", {})
    media_files = len(media_payload) if isinstance(media_payload, dict) else 0
    plan = {
        "requiresConfirmation": True,
        "storeSnapshot": store_snapshot is not None,
        "authSnapshot": True,
        "mediaFiles": media_files,
    }
    if dry_run:
        return plan
    if not confirm_replace:
        raise ValueError("Restore can replace protected runtime data; rerun with --confirm-replace to continue.")

    store = create_persist_store()
    auth = AuthStore()
    if restore_runtime_data:
        store.save_snapshot({} if store_snapshot is None else dict(store_snapshot))
        auth.import_snapshot(dict(auth_snapshot), replace=True)
    restored_media = 0
    if target_media_root is not None:
        restored_media = _restore_media_payload(payload, Path(target_media_root))
    report = {
        "applied": {"storeSnapshot": bool(restore_runtime_data), "authSnapshot": bool(restore_runtime_data), "mediaFiles": restored_media},
        "postRestoreStatus": collect_data_safety_status().to_api_dict(),
    }
    append_data_safety_audit_event(
        audit_path or (REPO_ROOT / "data" / "data-safety-audit.jsonl"),
        new_data_safety_audit_event(
            event_id=f"restore-{source.stem}",
            actor="operator",
            operation_type="restore",
            operation_id=source.name,
            result="ok",
            protected_classes=("auth-users", "project-store", "media-assets"),
            inputs_summary={"mediaFiles": restored_media, "restoreRuntimeData": restore_runtime_data},
        ),
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a LearningPyramid runtime state backup bundle.")
    parser.add_argument("input", type=Path, help="Path to the backup bundle JSON")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be restored without applying changes")
    parser.add_argument("--confirm-replace", action="store_true", help="Explicitly confirm replacing protected runtime data")
    parser.add_argument("--target-media-root", type=Path, default=None, help="Root directory for restored media payload")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = restore_runtime_bundle(input_path=Path(args.input), dry_run=bool(args.dry_run), confirm_replace=bool(args.confirm_replace), target_media_root=args.target_media_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
