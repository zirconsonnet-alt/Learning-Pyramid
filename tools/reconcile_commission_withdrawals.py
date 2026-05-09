import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapter.deps import get_membership_commission_store, get_membership_payment_service
from backend.system.membership_maintenance import reconcile_commission_withdrawals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile in-flight commission withdrawals by querying WeChat merchant transfer bill status."
    )
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=2,
        help="Only inspect awaiting-confirmation or processing withdrawals at least this many minutes old. Default: 2",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of withdrawals to inspect. Default: 100")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation for stdout output. Default: 2")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = reconcile_commission_withdrawals(
        get_membership_commission_store(),
        get_membership_payment_service(),
        min_age_minutes=args.min_age_minutes,
        limit=args.limit,
    )
    json.dump(summary.to_dict(), sys.stdout, ensure_ascii=False, indent=max(0, int(args.indent)))
    sys.stdout.write("\n")
    return 1 if summary.error_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
