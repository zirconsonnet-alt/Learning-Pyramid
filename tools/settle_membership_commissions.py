import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapter.deps import get_membership_commission_store
from backend.system.membership_maintenance import settle_due_membership_commissions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Settle eligible invite commissions after the refund window and write an idempotent run summary."
    )
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of pending commission records to inspect. Default: 200")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation for stdout output. Default: 2")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = settle_due_membership_commissions(
        get_membership_commission_store(),
        limit=args.limit,
    )
    json.dump(summary.to_dict(), sys.stdout, ensure_ascii=False, indent=max(0, int(args.indent)))
    sys.stdout.write("\n")
    return 1 if summary.error_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
