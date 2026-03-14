from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.auth_store import AuthStore
from backend.system.sql_backend import create_persist_store, current_sql_runtime_config
from backend.system.version import APP_VERSION


def backup_runtime_bundle(*, output_path: Path) -> Path:
    cfg = current_sql_runtime_config()
    store = create_persist_store(legacy_root=REPO_ROOT)
    auth = AuthStore()
    payload = {
        "metadata": {
            "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "appVersion": APP_VERSION,
            "sqlBackend": cfg.backend,
        },
        "storeSnapshot": store.load_snapshot(),
        "authSnapshot": auth.export_snapshot(),
    }
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup the current LearningPyramid runtime state into a JSON bundle.")
    parser.add_argument("output", type=Path, help="Path to write the backup bundle JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    backup_runtime_bundle(output_path=Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
