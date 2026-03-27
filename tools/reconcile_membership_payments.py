from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapter.deps import get_membership_payment_service, get_membership_store
from backend.system.membership_maintenance import (
    current_membership_pending_payment_reconcile_config,
    reconcile_pending_wechat_membership_payments,
)


def build_parser() -> argparse.ArgumentParser:
    defaults = current_membership_pending_payment_reconcile_config()
    parser = argparse.ArgumentParser(
        description="Reconcile pending wechat_native membership payments and sync remote terminal states back into the local order store."
    )
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=defaults.min_age_minutes,
        help=f"Only inspect pending wechat_native orders created at least this many minutes ago. Default: {defaults.min_age_minutes}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=defaults.limit,
        help=f"Maximum number of pending orders to inspect in one run. Default: {defaults.limit}",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation for stdout output. Default: 2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    membership_store = get_membership_store()
    membership_payment_service = get_membership_payment_service()
    summary = reconcile_pending_wechat_membership_payments(
        membership_store,
        membership_payment_service,
        min_age_minutes=args.min_age_minutes,
        limit=args.limit,
    )
    json.dump(summary.to_dict(), sys.stdout, ensure_ascii=False, indent=max(0, int(args.indent)))
    sys.stdout.write("\n")
    return 1 if summary.error_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
