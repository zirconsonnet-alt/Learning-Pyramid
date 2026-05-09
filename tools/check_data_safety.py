import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.system.data_safety import collect_data_safety_status, scan_media_references


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run data-safety integrity checks.")
    parser.add_argument("--media-references", type=Path, help="JSON file containing media reference records")
    parser.add_argument("--media-root", action="append", type=Path, default=[], help="Media root to scan for orphaned files")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    references: list[dict[str, object]] = []
    if args.media_references:
        raw = json.loads(args.media_references.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("--media-references must point to a JSON array")
        references = [dict(item) for item in raw if isinstance(item, dict)]
    findings = scan_media_references(references, media_roots=tuple(args.media_root))
    payload = collect_data_safety_status(findings=findings).to_api_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"state={payload['state']} findings={len(payload['findings'])}")
    return 1 if payload["releaseBlocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
