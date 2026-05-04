from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.models.errors import NotFound, PreconditionFailure
from backend.system.app_paths import resolve_membership_db_path

COMMISSION_STATUS_PENDING = "pending"
COMMISSION_STATUS_SETTLED = "settled"
COMMISSION_STATUS_CANCELED = "canceled"
COMMISSION_STATUS_REVERSED = "reversed"

WITHDRAWAL_STATUS_PENDING = "pending"
WITHDRAWAL_STATUS_PROCESSING = "processing"
WITHDRAWAL_STATUS_SUCCEEDED = "succeeded"
WITHDRAWAL_STATUS_FAILED = "failed"
WITHDRAWAL_STATUS_CANCELED = "canceled"

COMMISSION_THRESHOLD_AMOUNT_CENT = 1500
COMMISSION_SETTLED_AMOUNT_CENT = 500
COMMISSION_REFUND_WINDOW_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_limit(limit: int, *, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


@dataclass(frozen=True, slots=True)
class CommissionRecord:
    commission_id: str
    inviter_user_id: str
    invitee_user_id: str
    source_order_id: str
    source_payment_amount_cent: int
    threshold_amount_cent: int
    commission_amount_cent: int
    refund_window_ends_at: str
    status: str
    created_at: str
    settled_at: str | None
    canceled_at: str | None
    cancel_reason: str


@dataclass(frozen=True, slots=True)
class CommissionAccountSummary:
    user_id: str
    pending_cent: int
    withdrawable_cent: int
    reserved_cent: int
    paid_out_cent: int
    canceled_cent: int
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class WithdrawalRequest:
    withdrawal_id: str
    user_id: str
    amount_cent: int
    target_type: str
    wechat_open_id: str
    status: str
    provider_transfer_no: str | None
    failure_reason: str
    created_at: str
    submitted_at: str | None
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class CommissionAdminOverview:
    pending_commission_cent: int
    withdrawable_commission_cent: int
    reserved_withdrawal_cent: int
    paid_out_cent: int
    commission_record_count: int
    withdrawal_count: int


@dataclass(frozen=True, slots=True)
class CommissionSettlementResult:
    settled_count: int
    canceled_count: int
    skipped_count: int


class MembershipCommissionStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = (db_path or resolve_membership_db_path()).expanduser().resolve()
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    f"""
                    CREATE TABLE IF NOT EXISTS commission_records (
                        commission_id TEXT PRIMARY KEY,
                        inviter_user_id TEXT NOT NULL,
                        invitee_user_id TEXT NOT NULL,
                        source_order_id TEXT NOT NULL UNIQUE,
                        source_payment_amount_cent INTEGER NOT NULL,
                        threshold_amount_cent INTEGER NOT NULL,
                        commission_amount_cent INTEGER NOT NULL,
                        refund_window_ends_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        settled_at TEXT,
                        canceled_at TEXT,
                        cancel_reason TEXT NOT NULL DEFAULT '',
                        CHECK (source_payment_amount_cent >= 0),
                        CHECK (threshold_amount_cent >= 0),
                        CHECK (commission_amount_cent >= 0),
                        CHECK (status IN ('{COMMISSION_STATUS_PENDING}', '{COMMISSION_STATUS_SETTLED}', '{COMMISSION_STATUS_CANCELED}', '{COMMISSION_STATUS_REVERSED}'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_commission_records_inviter
                    ON commission_records (inviter_user_id, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_commission_records_status
                    ON commission_records (status, refund_window_ends_at ASC, created_at ASC);

                    CREATE TABLE IF NOT EXISTS commission_withdrawal_requests (
                        withdrawal_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        amount_cent INTEGER NOT NULL,
                        target_type TEXT NOT NULL,
                        wechat_open_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        provider_transfer_no TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        submitted_at TEXT,
                        completed_at TEXT,
                        CHECK (amount_cent > 0),
                        CHECK (status IN ('{WITHDRAWAL_STATUS_PENDING}', '{WITHDRAWAL_STATUS_PROCESSING}', '{WITHDRAWAL_STATUS_SUCCEEDED}', '{WITHDRAWAL_STATUS_FAILED}', '{WITHDRAWAL_STATUS_CANCELED}'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_user
                    ON commission_withdrawal_requests (user_id, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_status
                    ON commission_withdrawal_requests (status, created_at DESC);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _row_to_commission(row: sqlite3.Row) -> CommissionRecord:
        return CommissionRecord(
            commission_id=str(row["commission_id"]),
            inviter_user_id=str(row["inviter_user_id"]),
            invitee_user_id=str(row["invitee_user_id"]),
            source_order_id=str(row["source_order_id"]),
            source_payment_amount_cent=int(row["source_payment_amount_cent"]),
            threshold_amount_cent=int(row["threshold_amount_cent"]),
            commission_amount_cent=int(row["commission_amount_cent"]),
            refund_window_ends_at=str(row["refund_window_ends_at"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            settled_at=None if row["settled_at"] is None else str(row["settled_at"]),
            canceled_at=None if row["canceled_at"] is None else str(row["canceled_at"]),
            cancel_reason=str(row["cancel_reason"] or ""),
        )

    @staticmethod
    def _row_to_withdrawal(row: sqlite3.Row) -> WithdrawalRequest:
        return WithdrawalRequest(
            withdrawal_id=str(row["withdrawal_id"]),
            user_id=str(row["user_id"]),
            amount_cent=int(row["amount_cent"]),
            target_type=str(row["target_type"]),
            wechat_open_id=str(row["wechat_open_id"]),
            status=str(row["status"]),
            provider_transfer_no=None if row["provider_transfer_no"] is None else str(row["provider_transfer_no"]),
            failure_reason=str(row["failure_reason"] or ""),
            created_at=str(row["created_at"]),
            submitted_at=None if row["submitted_at"] is None else str(row["submitted_at"]),
            completed_at=None if row["completed_at"] is None else str(row["completed_at"]),
        )

    def get_commission_for_order(self, source_order_id: str) -> CommissionRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM commission_records WHERE source_order_id = ? LIMIT 1",
                (str(source_order_id),),
            ).fetchone()
            return None if row is None else self._row_to_commission(row)
        finally:
            conn.close()

    def get_withdrawal_request(self, withdrawal_id: str) -> WithdrawalRequest | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                (str(withdrawal_id),),
            ).fetchone()
            return None if row is None else self._row_to_withdrawal(row)
        finally:
            conn.close()

    def create_pending_commission(
        self,
        *,
        inviter_user_id: str,
        invitee_user_id: str,
        source_order_id: str,
        source_payment_amount_cent: int,
        paid_at: str,
    ) -> CommissionRecord | None:
        normalized_amount = max(0, int(source_payment_amount_cent))
        if normalized_amount < COMMISSION_THRESHOLD_AMOUNT_CENT:
            return None
        paid_at_dt = datetime.fromisoformat(str(paid_at))
        if paid_at_dt.tzinfo is None:
            paid_at_dt = paid_at_dt.replace(tzinfo=timezone.utc)
        else:
            paid_at_dt = paid_at_dt.astimezone(timezone.utc)
        refund_window_ends_at = (paid_at_dt + timedelta(hours=COMMISSION_REFUND_WINDOW_HOURS)).replace(microsecond=0).isoformat()
        created_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT * FROM commission_records WHERE source_order_id = ? LIMIT 1",
                    (str(source_order_id),),
                ).fetchone()
                if existing is not None:
                    return self._row_to_commission(existing)
                commission_id = f"mcom_{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO commission_records (
                        commission_id,
                        inviter_user_id,
                        invitee_user_id,
                        source_order_id,
                        source_payment_amount_cent,
                        threshold_amount_cent,
                        commission_amount_cent,
                        refund_window_ends_at,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        commission_id,
                        str(inviter_user_id),
                        str(invitee_user_id),
                        str(source_order_id),
                        normalized_amount,
                        COMMISSION_THRESHOLD_AMOUNT_CENT,
                        COMMISSION_SETTLED_AMOUNT_CENT,
                        refund_window_ends_at,
                        COMMISSION_STATUS_PENDING,
                        created_at,
                    ),
                )
                row = conn.execute("SELECT * FROM commission_records WHERE commission_id = ? LIMIT 1", (commission_id,)).fetchone()
                conn.commit()
                return None if row is None else self._row_to_commission(row)
            finally:
                conn.close()

    def cancel_pending_commission_for_order(self, source_order_id: str, *, reason: str) -> CommissionRecord | None:
        canceled_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM commission_records WHERE source_order_id = ? LIMIT 1",
                    (str(source_order_id),),
                ).fetchone()
                if row is None:
                    return None
                commission = self._row_to_commission(row)
                if commission.status != COMMISSION_STATUS_PENDING:
                    return commission
                conn.execute(
                    """
                    UPDATE commission_records
                    SET status = ?, canceled_at = ?, cancel_reason = ?
                    WHERE commission_id = ?
                    """,
                    (COMMISSION_STATUS_CANCELED, canceled_at, str(reason or ""), commission.commission_id),
                )
                updated = conn.execute(
                    "SELECT * FROM commission_records WHERE commission_id = ? LIMIT 1",
                    (commission.commission_id,),
                ).fetchone()
                conn.commit()
                return None if updated is None else self._row_to_commission(updated)
            finally:
                conn.close()

    def settle_due_commissions(self, *, now: datetime | None = None) -> CommissionSettlementResult:
        resolved_now = now or _utc_now()
        now_text = resolved_now.isoformat()
        settled_count = 0
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT commission_id
                    FROM commission_records
                    WHERE status = ?
                      AND refund_window_ends_at <= ?
                    ORDER BY refund_window_ends_at ASC, created_at ASC
                    """,
                    (COMMISSION_STATUS_PENDING, now_text),
                ).fetchall()
                for row in rows:
                    source_order_row = conn.execute(
                        "SELECT invitee_user_id FROM commission_records WHERE commission_id = ? LIMIT 1",
                        (str(row["commission_id"]),),
                    ).fetchone()
                    conn.execute(
                        """
                        UPDATE commission_records
                        SET status = ?, settled_at = ?
                        WHERE commission_id = ?
                        """,
                        (COMMISSION_STATUS_SETTLED, now_text, str(row["commission_id"])),
                    )
                    if source_order_row is not None:
                        conn.execute(
                            """
                            UPDATE invite_bindings
                            SET status = ?
                            WHERE invitee_user_id = ?
                              AND status = ?
                            """,
                            ("commission_settled", str(source_order_row["invitee_user_id"]), "commission_pending"),
                        )
                    settled_count += 1
                conn.commit()
            finally:
                conn.close()
        return CommissionSettlementResult(settled_count=settled_count, canceled_count=0, skipped_count=0)

    def list_user_commissions(self, user_id: str, *, limit: int = 20) -> tuple[CommissionRecord, ...]:
        normalized_limit = _normalize_limit(limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM commission_records
                WHERE inviter_user_id = ?
                ORDER BY created_at DESC, commission_id DESC
                LIMIT ?
                """,
                (str(user_id), normalized_limit),
            ).fetchall()
            return tuple(self._row_to_commission(row) for row in rows)
        finally:
            conn.close()

    def list_admin_commissions(self, *, status: str | None = None, limit: int = 100) -> tuple[CommissionRecord, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        where = ""
        params: list[object] = []
        if status and str(status).strip().lower() != "all":
            where = "WHERE status = ?"
            params.append(str(status).strip().lower())
        params.append(normalized_limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM commission_records
                {where}
                ORDER BY created_at DESC, commission_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_commission(row) for row in rows)
        finally:
            conn.close()

    def get_user_account(self, user_id: str) -> CommissionAccountSummary:
        conn = self._connect()
        try:
            pending = conn.execute(
                "SELECT COALESCE(SUM(commission_amount_cent), 0) AS total FROM commission_records WHERE inviter_user_id = ? AND status = ?",
                (str(user_id), COMMISSION_STATUS_PENDING),
            ).fetchone()
            settled = conn.execute(
                "SELECT COALESCE(SUM(commission_amount_cent), 0) AS total FROM commission_records WHERE inviter_user_id = ? AND status = ?",
                (str(user_id), COMMISSION_STATUS_SETTLED),
            ).fetchone()
            canceled = conn.execute(
                "SELECT COALESCE(SUM(commission_amount_cent), 0) AS total FROM commission_records WHERE inviter_user_id = ? AND status = ?",
                (str(user_id), COMMISSION_STATUS_CANCELED),
            ).fetchone()
            reserved = conn.execute(
                "SELECT COALESCE(SUM(amount_cent), 0) AS total FROM commission_withdrawal_requests WHERE user_id = ? AND status IN (?, ?)",
                (str(user_id), WITHDRAWAL_STATUS_PENDING, WITHDRAWAL_STATUS_PROCESSING),
            ).fetchone()
            paid_out = conn.execute(
                "SELECT COALESCE(SUM(amount_cent), 0) AS total FROM commission_withdrawal_requests WHERE user_id = ? AND status = ?",
                (str(user_id), WITHDRAWAL_STATUS_SUCCEEDED),
            ).fetchone()
            timestamps = conn.execute(
                """
                SELECT MAX(ts) AS updated_at
                FROM (
                    SELECT MAX(created_at) AS ts FROM commission_records WHERE inviter_user_id = ?
                    UNION ALL
                    SELECT MAX(created_at) AS ts FROM commission_withdrawal_requests WHERE user_id = ?
                )
                """,
                (str(user_id), str(user_id)),
            ).fetchone()
            settled_total = 0 if settled is None else int(settled["total"] or 0)
            reserved_total = 0 if reserved is None else int(reserved["total"] or 0)
            paid_out_total = 0 if paid_out is None else int(paid_out["total"] or 0)
            withdrawable = max(0, settled_total - reserved_total - paid_out_total)
            return CommissionAccountSummary(
                user_id=str(user_id),
                pending_cent=0 if pending is None else int(pending["total"] or 0),
                withdrawable_cent=withdrawable,
                reserved_cent=reserved_total,
                paid_out_cent=paid_out_total,
                canceled_cent=0 if canceled is None else int(canceled["total"] or 0),
                updated_at=None if timestamps is None or timestamps["updated_at"] is None else str(timestamps["updated_at"]),
            )
        finally:
            conn.close()

    def create_withdrawal_request(self, user_id: str, *, amount_cent: int, wechat_open_id: str) -> WithdrawalRequest:
        normalized_amount = int(amount_cent)
        normalized_open_id = str(wechat_open_id or "").strip()
        if normalized_amount <= 0:
            raise PreconditionFailure("withdrawal amount must be positive")
        if not normalized_open_id:
            raise PreconditionFailure("wechat receiving identity is required")
        account = self.get_user_account(user_id)
        if normalized_amount > account.withdrawable_cent:
            raise PreconditionFailure("withdrawal amount exceeds withdrawable commission balance")
        withdrawal_id = f"mwd_{uuid.uuid4().hex}"
        created_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO commission_withdrawal_requests (
                        withdrawal_id,
                        user_id,
                        amount_cent,
                        target_type,
                        wechat_open_id,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, 'wechat_pay', ?, ?, ?)
                    """,
                    (withdrawal_id, str(user_id), normalized_amount, normalized_open_id, WITHDRAWAL_STATUS_PENDING, created_at),
                )
                row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (withdrawal_id,),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("withdrawal request")
                return self._row_to_withdrawal(row)
            finally:
                conn.close()

    def mark_withdrawal_processing(self, withdrawal_id: str, *, provider_transfer_no: str | None) -> WithdrawalRequest:
        submitted_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                current_row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                if current_row is None:
                    raise NotFound("withdrawal request")
                current = self._row_to_withdrawal(current_row)
                if current.status != WITHDRAWAL_STATUS_PENDING:
                    return current
                conn.execute(
                    """
                    UPDATE commission_withdrawal_requests
                    SET status = ?, provider_transfer_no = ?, submitted_at = ?
                    WHERE withdrawal_id = ?
                    """,
                    (WITHDRAWAL_STATUS_PROCESSING, str(provider_transfer_no or "") or None, submitted_at, str(withdrawal_id)),
                )
                row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("withdrawal request")
                conn.commit()
                return self._row_to_withdrawal(row)
            finally:
                conn.close()

    def mark_withdrawal_succeeded(self, withdrawal_id: str, *, provider_transfer_no: str | None = None, completed_at: str | None = None) -> WithdrawalRequest:
        resolved_completed_at = str(completed_at or _utc_now().isoformat())
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("withdrawal request")
                current = self._row_to_withdrawal(row)
                if current.status == WITHDRAWAL_STATUS_SUCCEEDED:
                    return current
                if current.status in {WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED}:
                    return current
                conn.execute(
                    """
                    UPDATE commission_withdrawal_requests
                    SET status = ?, provider_transfer_no = COALESCE(?, provider_transfer_no), completed_at = ?, failure_reason = ''
                    WHERE withdrawal_id = ?
                    """,
                    (WITHDRAWAL_STATUS_SUCCEEDED, str(provider_transfer_no or "") or None, resolved_completed_at, str(withdrawal_id)),
                )
                updated = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("withdrawal request")
                return self._row_to_withdrawal(updated)
            finally:
                conn.close()

    def mark_withdrawal_failed(self, withdrawal_id: str, *, failure_reason: str, provider_transfer_no: str | None = None, completed_at: str | None = None) -> WithdrawalRequest:
        resolved_completed_at = str(completed_at or _utc_now().isoformat())
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("withdrawal request")
                current = self._row_to_withdrawal(row)
                if current.status == WITHDRAWAL_STATUS_FAILED:
                    return current
                if current.status in {WITHDRAWAL_STATUS_SUCCEEDED, WITHDRAWAL_STATUS_CANCELED}:
                    return current
                conn.execute(
                    """
                    UPDATE commission_withdrawal_requests
                    SET status = ?, provider_transfer_no = COALESCE(?, provider_transfer_no), completed_at = ?, failure_reason = ?
                    WHERE withdrawal_id = ?
                    """,
                    (WITHDRAWAL_STATUS_FAILED, str(provider_transfer_no or "") or None, resolved_completed_at, str(failure_reason or ""), str(withdrawal_id)),
                )
                updated = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("withdrawal request")
                return self._row_to_withdrawal(updated)
            finally:
                conn.close()

    def list_user_withdrawals(self, user_id: str, *, limit: int = 20) -> tuple[WithdrawalRequest, ...]:
        normalized_limit = _normalize_limit(limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM commission_withdrawal_requests
                WHERE user_id = ?
                ORDER BY created_at DESC, withdrawal_id DESC
                LIMIT ?
                """,
                (str(user_id), normalized_limit),
            ).fetchall()
            return tuple(self._row_to_withdrawal(row) for row in rows)
        finally:
            conn.close()

    def list_admin_withdrawals(self, *, status: str | None = None, limit: int = 100) -> tuple[WithdrawalRequest, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        where = ""
        params: list[object] = []
        if status and str(status).strip().lower() != "all":
            where = "WHERE status = ?"
            params.append(str(status).strip().lower())
        params.append(normalized_limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM commission_withdrawal_requests
                {where}
                ORDER BY created_at DESC, withdrawal_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_withdrawal(row) for row in rows)
        finally:
            conn.close()

    def get_admin_overview(self) -> CommissionAdminOverview:
        account = self.get_user_account("__aggregate__")
        conn = self._connect()
        try:
            commission_count = conn.execute("SELECT COUNT(*) AS total FROM commission_records").fetchone()
            withdrawal_count = conn.execute("SELECT COUNT(*) AS total FROM commission_withdrawal_requests").fetchone()
            pending = conn.execute(
                "SELECT COALESCE(SUM(commission_amount_cent), 0) AS total FROM commission_records WHERE status = ?",
                (COMMISSION_STATUS_PENDING,),
            ).fetchone()
            settled = conn.execute(
                "SELECT COALESCE(SUM(commission_amount_cent), 0) AS total FROM commission_records WHERE status = ?",
                (COMMISSION_STATUS_SETTLED,),
            ).fetchone()
            reserved = conn.execute(
                "SELECT COALESCE(SUM(amount_cent), 0) AS total FROM commission_withdrawal_requests WHERE status IN (?, ?)",
                (WITHDRAWAL_STATUS_PENDING, WITHDRAWAL_STATUS_PROCESSING),
            ).fetchone()
            paid_out = conn.execute(
                "SELECT COALESCE(SUM(amount_cent), 0) AS total FROM commission_withdrawal_requests WHERE status = ?",
                (WITHDRAWAL_STATUS_SUCCEEDED,),
            ).fetchone()
            settled_total = 0 if settled is None else int(settled["total"] or 0)
            reserved_total = 0 if reserved is None else int(reserved["total"] or 0)
            paid_out_total = 0 if paid_out is None else int(paid_out["total"] or 0)
            return CommissionAdminOverview(
                pending_commission_cent=0 if pending is None else int(pending["total"] or 0),
                withdrawable_commission_cent=max(0, settled_total - reserved_total - paid_out_total),
                reserved_withdrawal_cent=reserved_total,
                paid_out_cent=paid_out_total,
                commission_record_count=0 if commission_count is None else int(commission_count["total"] or 0),
                withdrawal_count=0 if withdrawal_count is None else int(withdrawal_count["total"] or 0),
            )
        finally:
            conn.close()
