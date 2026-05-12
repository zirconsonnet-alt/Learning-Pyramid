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


def test_mark_withdrawal_processing_updates_awaiting_confirmation_request(tmp_path):
    db_path = tmp_path / "membership.sqlite3"
    store = MembershipCommissionStore(db_path)
    now = datetime(2026, 5, 12, 5, 0, tzinfo=timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO commission_withdrawal_requests (
                withdrawal_id, user_id, amount_cent, target_type, wechat_open_id,
                status, provider_transfer_no, created_at, submitted_at, reserved_at,
                confirmation_requested_at, identity_masked_label, out_bill_no,
                transfer_bill_no, package_info, provider_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mwd_confirm",
                "user_inviter",
                500,
                "wechat_pay",
                "openid_e2e",
                "awaiting_confirmation",
                "transfer_e2e",
                now,
                now,
                now,
                now,
                "openid***",
                "LPWD_E2E",
                "transfer_e2e",
                "package_e2e",
                "WAIT_USER_CONFIRM",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    updated = store.mark_withdrawal_processing(
        "mwd_confirm",
        provider_transfer_no="transfer_e2e",
        provider_state="USER_CONFIRMED",
        raw_payload_json='{"source":"wechat_jsapi_requestMerchantTransfer"}',
    )

    assert updated.status == "processing"
    assert updated.provider_state == "USER_CONFIRMED"
    assert updated.provider_transfer_no == "transfer_e2e"
    assert updated.transfer_bill_no == "transfer_e2e"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        event = conn.execute(
            "SELECT event_type, mapped_status, provider_state, raw_payload_json FROM payout_provider_events WHERE withdrawal_id = ?",
            ("mwd_confirm",),
        ).fetchone()
    finally:
        conn.close()

    assert event is not None
    assert event["event_type"] == "create_response"
    assert event["mapped_status"] == "processing"
    assert event["provider_state"] == "USER_CONFIRMED"
    assert event["raw_payload_json"] == '{"source":"wechat_jsapi_requestMerchantTransfer"}'
