import sqlite3
from datetime import datetime, timedelta, timezone

from backend.system.membership_commission_store import MembershipCommissionStore


def test_settle_due_commissions_settles_due_pending_commission(tmp_path):
    db_path = tmp_path / "membership.sqlite3"
    store = MembershipCommissionStore(db_path)
    now = datetime(2026, 5, 11, 16, 0, tzinfo=timezone.utc)
    refund_window_ends_at = (now - timedelta(minutes=1)).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO commission_records (
                commission_id, inviter_user_id, invitee_user_id, source_order_id,
                source_payment_amount_cent, threshold_amount_cent, commission_amount_cent,
                refund_window_ends_at, status, created_at, settlement_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mcom_due",
                "user_inviter",
                "user_invitee",
                "mord_paid",
                2000,
                1500,
                500,
                refund_window_ends_at,
                "pending",
                (now - timedelta(minutes=2)).isoformat(),
                "automatic",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    result = store.settle_due_commissions(now=now, limit=200)

    assert result.scanned_count == 1
    assert result.settled_count == 1
    assert result.error_count == 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT status, settled_at, settlement_run_id FROM commission_records WHERE commission_id = ?", ("mcom_due",)).fetchone()
        run = conn.execute("SELECT run_type, scanned_count, settled_count, error_count FROM reconciliation_runs WHERE run_id = ?", (result.run_id,)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "settled"
    assert row["settled_at"] == now.isoformat()
    assert row["settlement_run_id"] == result.run_id
    assert run is not None
    assert run["run_type"] == "commission_settlement"
    assert run["scanned_count"] == 1
    assert run["settled_count"] == 1
    assert run["error_count"] == 0
