from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.auth_store import AuthStore
from backend.system.sql_backend import create_persist_store


def restore_runtime_bundle(*, input_path: Path) -> None:
    source = Path(input_path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup bundle must be a JSON object")

    store_snapshot = payload.get("storeSnapshot")
    auth_snapshot = payload.get("authSnapshot")
    if store_snapshot is not None and not isinstance(store_snapshot, dict):
        raise ValueError("storeSnapshot must be a JSON object or null")
    if auth_snapshot is None or not isinstance(auth_snapshot, dict):
        raise ValueError("authSnapshot must be a JSON object")

    store = create_persist_store(legacy_root=REPO_ROOT)
    auth = AuthStore()
    store.save_snapshot({} if store_snapshot is None else dict(store_snapshot))
    auth.import_snapshot(dict(auth_snapshot), replace=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a LearningPyramid runtime state backup bundle.")
    parser.add_argument("input", type=Path, help="Path to the backup bundle JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    restore_runtime_bundle(input_path=Path(args.input))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
