from __future__ import annotations

import json
import os
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

WITHDRAWAL_STATUS_CREATED = "created"
WITHDRAWAL_STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
WITHDRAWAL_STATUS_PROCESSING = "processing"
WITHDRAWAL_STATUS_SUCCEEDED = "succeeded"
WITHDRAWAL_STATUS_FAILED = "failed"
WITHDRAWAL_STATUS_CANCELED = "canceled"
WITHDRAWAL_STATUS_NEEDS_ATTENTION = "needs_attention"
WITHDRAWAL_STATUS_PENDING = WITHDRAWAL_STATUS_CREATED

BINDING_STATUS_CREATED = "created"
BINDING_STATUS_SCANNED = "scanned"
BINDING_STATUS_AUTHORIZED = "authorized"
BINDING_STATUS_CONFIRMED = "confirmed"
BINDING_STATUS_BOUND = "bound"
BINDING_STATUS_FAILED = "failed"
BINDING_STATUS_CANCELED = "canceled"
BINDING_STATUS_EXPIRED = "expired"

PAYOUT_PROVIDER_WECHAT_PAY = "wechat_pay"
PAYOUT_PROVIDER_MANUAL_TEST = "manual_test"

PAYOUT_IDENTITY_STATUS_ACTIVE = "active"
PAYOUT_IDENTITY_STATUS_REPLACED = "replaced"

COMMISSION_THRESHOLD_AMOUNT_CENT = 1500
COMMISSION_SETTLED_AMOUNT_CENT = 500
COMMISSION_REFUND_WINDOW_HOURS = 24
COMMISSION_REFUND_WINDOW_ENV = "PLM_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_limit(limit: int, *, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


def commission_refund_window_minutes() -> int:
    raw = str(os.getenv(COMMISSION_REFUND_WINDOW_ENV) or "").strip()
    if not raw:
        return COMMISSION_REFUND_WINDOW_HOURS * 60
    try:
        value = int(raw)
    except Exception:
        return COMMISSION_REFUND_WINDOW_HOURS * 60
    return max(1, min(value, 30 * 24 * 60))


def _parse_dt(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value or _utc_now().isoformat()))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _row_get(row: sqlite3.Row, key: str, default: object = None) -> object:
    return row[key] if key in row.keys() else default


def _mask_openid(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 6:
        return f"{text[:1]}***"
    return f"{text[:7]}***"


def _new_out_bill_no() -> str:
    return f"LPWD{uuid.uuid4().hex[:28].upper()}"


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
    settlement_mode: str = ""
    last_settlement_checked_at: str | None = None
    settlement_run_id: str | None = None
    settlement_failure_reason: str = ""


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
class PayoutIdentity:
    identity_id: str
    user_id: str
    provider: str
    appid: str
    openid: str
    masked_openid: str
    status: str
    verified_at: str
    revoked_at: str | None
    latest_binding_attempt_id: str | None
    failure_reason: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PayoutBindingAttempt:
    binding_attempt_id: str
    user_id: str
    provider: str
    channel: str
    state: str
    status: str
    desktop_return_url: str
    mobile_binding_url: str
    qr_expires_at: str | None
    scanned_at: str | None
    confirmed_at: str | None
    authorization_code_hash: str
    resolved_openid: str
    identity_id: str | None
    failure_reason: str
    created_at: str
    authorized_at: str | None
    completed_at: str | None
    expires_at: str


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
    identity_id: str | None = None
    identity_masked_label: str = ""
    out_bill_no: str = ""
    transfer_bill_no: str | None = None
    package_info: str | None = None
    provider_state: str = ""
    reserved_at: str | None = None
    confirmation_requested_at: str | None = None


@dataclass(frozen=True, slots=True)
class PayoutProviderEvent:
    event_id: str
    withdrawal_id: str
    event_type: str
    provider: str
    provider_event_id: str
    out_bill_no: str
    transfer_bill_no: str | None
    provider_state: str
    mapped_status: str
    raw_payload_json: str
    signature_verified: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class ReconciliationRun:
    run_id: str
    run_type: str
    started_at: str
    finished_at: str
    limit: int
    scanned_count: int
    settled_count: int
    canceled_count: int
    succeeded_count: int
    failed_count: int
    needs_attention_count: int
    error_count: int
    summary_json: str


@dataclass(frozen=True, slots=True)
class ReconciliationWarning:
    warning_id: str
    withdrawal_id: str
    severity: str
    reason_code: str
    message: str
    status: str
    created_at: str
    resolved_at: str | None


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
    run_id: str = ""
    scanned_count: int = 0
    error_count: int = 0
    started_at: str = ""
    finished_at: str = ""


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

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (str(table),),
        ).fetchone()
        return row is not None

    @classmethod
    def _ensure_columns(cls, conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = cls._table_columns(conn, table)
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    @classmethod
    def _ensure_withdrawal_status_schema(cls, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'commission_withdrawal_requests' LIMIT 1"
        ).fetchone()
        table_sql = "" if row is None or row["sql"] is None else str(row["sql"]).lower()
        if not table_sql:
            return
        has_legacy_check = "check" in table_sql and "status" in table_sql and "'pending'" in table_sql
        has_legacy_pending_rows = (
            conn.execute("SELECT 1 FROM commission_withdrawal_requests WHERE status = 'pending' LIMIT 1").fetchone() is not None
        )
        if not has_legacy_check:
            if has_legacy_pending_rows:
                conn.execute("UPDATE commission_withdrawal_requests SET status = ? WHERE status = 'pending'", (WITHDRAWAL_STATUS_CREATED,))
            return

        legacy_table = f"commission_withdrawal_requests_legacy_{uuid.uuid4().hex}"
        for index_name in (
            "idx_commission_withdrawal_user",
            "idx_commission_withdrawal_status",
            "idx_commission_withdrawal_out_bill_no",
        ):
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        conn.execute(f"ALTER TABLE commission_withdrawal_requests RENAME TO {legacy_table}")
        conn.execute(
            """
            CREATE TABLE commission_withdrawal_requests (
                withdrawal_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount_cent INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                wechat_open_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                provider_transfer_no TEXT,
                failure_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                submitted_at TEXT,
                completed_at TEXT,
                identity_id TEXT,
                identity_masked_label TEXT NOT NULL DEFAULT '',
                out_bill_no TEXT NOT NULL DEFAULT '',
                transfer_bill_no TEXT,
                package_info TEXT,
                provider_state TEXT NOT NULL DEFAULT '',
                reserved_at TEXT,
                confirmation_requested_at TEXT
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO commission_withdrawal_requests (
                withdrawal_id, user_id, amount_cent, target_type, wechat_open_id, status,
                provider_transfer_no, failure_reason, created_at, submitted_at, completed_at,
                identity_id, identity_masked_label, out_bill_no, transfer_bill_no, package_info,
                provider_state, reserved_at, confirmation_requested_at
            )
            SELECT
                withdrawal_id,
                user_id,
                amount_cent,
                target_type,
                COALESCE(wechat_open_id, ''),
                CASE status WHEN 'pending' THEN ? ELSE status END,
                provider_transfer_no,
                COALESCE(failure_reason, ''),
                created_at,
                submitted_at,
                completed_at,
                identity_id,
                COALESCE(identity_masked_label, ''),
                COALESCE(out_bill_no, ''),
                transfer_bill_no,
                package_info,
                COALESCE(provider_state, ''),
                reserved_at,
                confirmation_requested_at
            FROM {legacy_table}
            """,
            (WITHDRAWAL_STATUS_CREATED,),
        )
        conn.execute(f"DROP TABLE {legacy_table}")

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
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
                        cancel_reason TEXT NOT NULL DEFAULT ''
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
                        wechat_open_id TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        provider_transfer_no TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        submitted_at TEXT,
                        completed_at TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_user
                    ON commission_withdrawal_requests (user_id, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_status
                    ON commission_withdrawal_requests (status, created_at DESC);

                    CREATE TABLE IF NOT EXISTS payout_identities (
                        identity_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        appid TEXT NOT NULL,
                        openid TEXT NOT NULL,
                        masked_openid TEXT NOT NULL,
                        status TEXT NOT NULL,
                        verified_at TEXT NOT NULL,
                        revoked_at TEXT,
                        latest_binding_attempt_id TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_payout_identities_user
                    ON payout_identities (user_id, provider, status, updated_at DESC);

                    CREATE TABLE IF NOT EXISTS payout_binding_attempts (
                        binding_attempt_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        state TEXT NOT NULL,
                        status TEXT NOT NULL,
                        desktop_return_url TEXT NOT NULL DEFAULT '',
                        mobile_binding_url TEXT NOT NULL DEFAULT '',
                        qr_expires_at TEXT,
                        scanned_at TEXT,
                        confirmed_at TEXT,
                        authorization_code_hash TEXT NOT NULL DEFAULT '',
                        resolved_openid TEXT NOT NULL DEFAULT '',
                        identity_id TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        authorized_at TEXT,
                        completed_at TEXT,
                        expires_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_payout_binding_attempts_user
                    ON payout_binding_attempts (user_id, created_at DESC);

                    CREATE TABLE IF NOT EXISTS payout_provider_events (
                        event_id TEXT PRIMARY KEY,
                        withdrawal_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        provider_event_id TEXT NOT NULL DEFAULT '',
                        out_bill_no TEXT NOT NULL DEFAULT '',
                        transfer_bill_no TEXT,
                        provider_state TEXT NOT NULL DEFAULT '',
                        mapped_status TEXT NOT NULL DEFAULT '',
                        raw_payload_json TEXT NOT NULL DEFAULT '',
                        signature_verified INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_payout_provider_events_withdrawal
                    ON payout_provider_events (withdrawal_id, created_at ASC);

                    CREATE TABLE IF NOT EXISTS reconciliation_runs (
                        run_id TEXT PRIMARY KEY,
                        run_type TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        finished_at TEXT NOT NULL,
                        limit_count INTEGER NOT NULL,
                        scanned_count INTEGER NOT NULL DEFAULT 0,
                        settled_count INTEGER NOT NULL DEFAULT 0,
                        canceled_count INTEGER NOT NULL DEFAULT 0,
                        succeeded_count INTEGER NOT NULL DEFAULT 0,
                        failed_count INTEGER NOT NULL DEFAULT 0,
                        needs_attention_count INTEGER NOT NULL DEFAULT 0,
                        error_count INTEGER NOT NULL DEFAULT 0,
                        summary_json TEXT NOT NULL DEFAULT ''
                    );

                    CREATE TABLE IF NOT EXISTS reconciliation_warnings (
                        warning_id TEXT PRIMARY KEY,
                        withdrawal_id TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        reason_code TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        resolved_at TEXT
                    );
                    """
                )
                self._ensure_columns(
                    conn,
                    "commission_records",
                    {
                        "settlement_mode": "TEXT NOT NULL DEFAULT ''",
                        "last_settlement_checked_at": "TEXT",
                        "settlement_run_id": "TEXT",
                        "settlement_failure_reason": "TEXT NOT NULL DEFAULT ''",
                    },
                )
                self._ensure_columns(
                    conn,
                    "commission_withdrawal_requests",
                    {
                        "identity_id": "TEXT",
                        "identity_masked_label": "TEXT NOT NULL DEFAULT ''",
                        "out_bill_no": "TEXT NOT NULL DEFAULT ''",
                        "transfer_bill_no": "TEXT",
                        "package_info": "TEXT",
                        "provider_state": "TEXT NOT NULL DEFAULT ''",
                        "reserved_at": "TEXT",
                        "confirmation_requested_at": "TEXT",
                    },
                )
                self._ensure_withdrawal_status_schema(conn)
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_user
                    ON commission_withdrawal_requests (user_id, created_at DESC)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_commission_withdrawal_status
                    ON commission_withdrawal_requests (status, created_at DESC)
                    """
                )
                self._ensure_columns(
                    conn,
                    "payout_binding_attempts",
                    {
                        "desktop_return_url": "TEXT NOT NULL DEFAULT ''",
                        "mobile_binding_url": "TEXT NOT NULL DEFAULT ''",
                        "qr_expires_at": "TEXT",
                        "scanned_at": "TEXT",
                        "confirmed_at": "TEXT",
                    },
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_withdrawal_out_bill_no ON commission_withdrawal_requests (out_bill_no) WHERE out_bill_no != ''"
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
            settlement_mode=str(_row_get(row, "settlement_mode", "") or ""),
            last_settlement_checked_at=None
            if _row_get(row, "last_settlement_checked_at") is None
            else str(_row_get(row, "last_settlement_checked_at")),
            settlement_run_id=None if _row_get(row, "settlement_run_id") is None else str(_row_get(row, "settlement_run_id")),
            settlement_failure_reason=str(_row_get(row, "settlement_failure_reason", "") or ""),
        )

    @staticmethod
    def _row_to_identity(row: sqlite3.Row) -> PayoutIdentity:
        return PayoutIdentity(
            identity_id=str(row["identity_id"]),
            user_id=str(row["user_id"]),
            provider=str(row["provider"]),
            appid=str(row["appid"]),
            openid=str(row["openid"]),
            masked_openid=str(row["masked_openid"]),
            status=str(row["status"]),
            verified_at=str(row["verified_at"]),
            revoked_at=None if row["revoked_at"] is None else str(row["revoked_at"]),
            latest_binding_attempt_id=None if row["latest_binding_attempt_id"] is None else str(row["latest_binding_attempt_id"]),
            failure_reason=str(row["failure_reason"] or ""),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_binding_attempt(row: sqlite3.Row) -> PayoutBindingAttempt:
        return PayoutBindingAttempt(
            binding_attempt_id=str(row["binding_attempt_id"]),
            user_id=str(row["user_id"]),
            provider=str(row["provider"]),
            channel=str(row["channel"]),
            state=str(row["state"]),
            status=str(row["status"]),
            desktop_return_url=str(row["desktop_return_url"] or ""),
            mobile_binding_url=str(row["mobile_binding_url"] or ""),
            qr_expires_at=None if row["qr_expires_at"] is None else str(row["qr_expires_at"]),
            scanned_at=None if row["scanned_at"] is None else str(row["scanned_at"]),
            confirmed_at=None if row["confirmed_at"] is None else str(row["confirmed_at"]),
            authorization_code_hash=str(row["authorization_code_hash"] or ""),
            resolved_openid=str(row["resolved_openid"] or ""),
            identity_id=None if row["identity_id"] is None else str(row["identity_id"]),
            failure_reason=str(row["failure_reason"] or ""),
            created_at=str(row["created_at"]),
            authorized_at=None if row["authorized_at"] is None else str(row["authorized_at"]),
            completed_at=None if row["completed_at"] is None else str(row["completed_at"]),
            expires_at=str(row["expires_at"]),
        )

    @staticmethod
    def _row_to_withdrawal(row: sqlite3.Row) -> WithdrawalRequest:
        return WithdrawalRequest(
            withdrawal_id=str(row["withdrawal_id"]),
            user_id=str(row["user_id"]),
            amount_cent=int(row["amount_cent"]),
            target_type=str(row["target_type"]),
            wechat_open_id=str(row["wechat_open_id"] or ""),
            status=str(row["status"]),
            provider_transfer_no=None if row["provider_transfer_no"] is None else str(row["provider_transfer_no"]),
            failure_reason=str(row["failure_reason"] or ""),
            created_at=str(row["created_at"]),
            submitted_at=None if row["submitted_at"] is None else str(row["submitted_at"]),
            completed_at=None if row["completed_at"] is None else str(row["completed_at"]),
            identity_id=None if _row_get(row, "identity_id") is None else str(_row_get(row, "identity_id")),
            identity_masked_label=str(_row_get(row, "identity_masked_label", "") or ""),
            out_bill_no=str(_row_get(row, "out_bill_no", "") or ""),
            transfer_bill_no=None if _row_get(row, "transfer_bill_no") is None else str(_row_get(row, "transfer_bill_no")),
            package_info=None if _row_get(row, "package_info") is None else str(_row_get(row, "package_info")),
            provider_state=str(_row_get(row, "provider_state", "") or ""),
            reserved_at=None if _row_get(row, "reserved_at") is None else str(_row_get(row, "reserved_at")),
            confirmation_requested_at=None
            if _row_get(row, "confirmation_requested_at") is None
            else str(_row_get(row, "confirmation_requested_at")),
        )

    @staticmethod
    def _row_to_provider_event(row: sqlite3.Row) -> PayoutProviderEvent:
        return PayoutProviderEvent(
            event_id=str(row["event_id"]),
            withdrawal_id=str(row["withdrawal_id"]),
            event_type=str(row["event_type"]),
            provider=str(row["provider"]),
            provider_event_id=str(row["provider_event_id"] or ""),
            out_bill_no=str(row["out_bill_no"] or ""),
            transfer_bill_no=None if row["transfer_bill_no"] is None else str(row["transfer_bill_no"]),
            provider_state=str(row["provider_state"] or ""),
            mapped_status=str(row["mapped_status"] or ""),
            raw_payload_json=str(row["raw_payload_json"] or ""),
            signature_verified=bool(row["signature_verified"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> ReconciliationRun:
        return ReconciliationRun(
            run_id=str(row["run_id"]),
            run_type=str(row["run_type"]),
            started_at=str(row["started_at"]),
            finished_at=str(row["finished_at"]),
            limit=int(row["limit_count"]),
            scanned_count=int(row["scanned_count"] or 0),
            settled_count=int(row["settled_count"] or 0),
            canceled_count=int(row["canceled_count"] or 0),
            succeeded_count=int(row["succeeded_count"] or 0),
            failed_count=int(row["failed_count"] or 0),
            needs_attention_count=int(row["needs_attention_count"] or 0),
            error_count=int(row["error_count"] or 0),
            summary_json=str(row["summary_json"] or ""),
        )

    @staticmethod
    def _row_to_warning(row: sqlite3.Row) -> ReconciliationWarning:
        return ReconciliationWarning(
            warning_id=str(row["warning_id"]),
            withdrawal_id=str(row["withdrawal_id"]),
            severity=str(row["severity"]),
            reason_code=str(row["reason_code"]),
            message=str(row["message"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            resolved_at=None if row["resolved_at"] is None else str(row["resolved_at"]),
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

    def get_withdrawal_by_out_bill_no(self, out_bill_no: str) -> WithdrawalRequest | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM commission_withdrawal_requests WHERE out_bill_no = ? LIMIT 1",
                (str(out_bill_no),),
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
        paid_at_dt = _parse_dt(paid_at)
        refund_window_ends_at = (paid_at_dt + timedelta(minutes=commission_refund_window_minutes())).replace(microsecond=0).isoformat()
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
                        commission_id, inviter_user_id, invitee_user_id, source_order_id,
                        source_payment_amount_cent, threshold_amount_cent, commission_amount_cent,
                        refund_window_ends_at, status, created_at, settlement_mode
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'automatic')
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
                updated = conn.execute("SELECT * FROM commission_records WHERE commission_id = ? LIMIT 1", (commission.commission_id,)).fetchone()
                conn.commit()
                return None if updated is None else self._row_to_commission(updated)
            finally:
                conn.close()

    def settle_due_commissions(self, *, now: datetime | None = None, limit: int = 200) -> CommissionSettlementResult:
        started = now or _utc_now()
        now_text = started.isoformat()
        normalized_limit = _normalize_limit(limit, default=200, maximum=1000)
        run_id = f"run_{uuid.uuid4().hex}"
        settled_count = 0
        canceled_count = 0
        skipped_count = 0
        error_count = 0
        scanned_count = 0
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM commission_records
                    WHERE status = ?
                      AND refund_window_ends_at <= ?
                    ORDER BY refund_window_ends_at ASC, created_at ASC
                    LIMIT ?
                    """,
                    (COMMISSION_STATUS_PENDING, now_text, normalized_limit),
                ).fetchall()
                scanned_count = len(rows)
                has_membership_orders = self._table_exists(conn, "membership_orders")
                has_invite_bindings = self._table_exists(conn, "invite_bindings")
                for row in rows:
                    commission = self._row_to_commission(row)
                    try:
                        order_row = (
                            conn.execute(
                                "SELECT status FROM membership_orders WHERE order_id = ? LIMIT 1",
                                (commission.source_order_id,),
                            ).fetchone()
                            if has_membership_orders
                            else None
                        )
                        if order_row is not None and str(order_row["status"]) in {"refund_pending", "refunded", "closed"}:
                            conn.execute(
                                """
                                UPDATE commission_records
                                SET status = ?, canceled_at = ?, cancel_reason = ?,
                                    settlement_mode = 'automatic',
                                    last_settlement_checked_at = ?,
                                    settlement_run_id = ?,
                                    settlement_failure_reason = ''
                                WHERE commission_id = ?
                                """,
                                (
                                    COMMISSION_STATUS_CANCELED,
                                    now_text,
                                    f"source order {order_row['status']}",
                                    now_text,
                                    run_id,
                                    commission.commission_id,
                                ),
                            )
                            canceled_count += 1
                        else:
                            conn.execute(
                                """
                                UPDATE commission_records
                                SET status = ?, settled_at = ?,
                                    settlement_mode = 'automatic',
                                    last_settlement_checked_at = ?,
                                    settlement_run_id = ?,
                                    settlement_failure_reason = ''
                                WHERE commission_id = ?
                                """,
                                (COMMISSION_STATUS_SETTLED, now_text, now_text, run_id, commission.commission_id),
                            )
                            if has_invite_bindings:
                                conn.execute(
                                    """
                                    UPDATE invite_bindings
                                    SET status = ?
                                    WHERE invitee_user_id = ?
                                      AND status = ?
                                    """,
                                    ("commission_settled", commission.invitee_user_id, "commission_pending"),
                                )
                            settled_count += 1
                    except Exception as exc:
                        error_count += 1
                        conn.execute(
                            """
                            UPDATE commission_records
                            SET last_settlement_checked_at = ?,
                                settlement_run_id = ?,
                                settlement_failure_reason = ?
                            WHERE commission_id = ?
                            """,
                            (now_text, run_id, str(exc), commission.commission_id),
                        )
                finished = _utc_now().isoformat()
                summary = {
                    "runId": run_id,
                    "runType": "commission_settlement",
                    "scannedCount": scanned_count,
                    "settledCount": settled_count,
                    "canceledCount": canceled_count,
                    "skippedCount": skipped_count,
                    "errorCount": error_count,
                }
                conn.execute(
                    """
                    INSERT INTO reconciliation_runs (
                        run_id, run_type, started_at, finished_at, limit_count, scanned_count,
                        settled_count, canceled_count, error_count, summary_json
                    )
                    VALUES (?, 'commission_settlement', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        started.isoformat(),
                        finished,
                        normalized_limit,
                        scanned_count,
                        settled_count,
                        canceled_count,
                        error_count,
                        json.dumps(summary, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return CommissionSettlementResult(
            settled_count=settled_count,
            canceled_count=canceled_count,
            skipped_count=skipped_count,
            run_id=run_id,
            scanned_count=scanned_count,
            error_count=error_count,
            started_at=started.isoformat(),
            finished_at=finished,
        )

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
        reserved_statuses = (
            WITHDRAWAL_STATUS_CREATED,
            WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
            WITHDRAWAL_STATUS_PROCESSING,
        )
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
                f"""
                SELECT COALESCE(SUM(amount_cent), 0) AS total
                FROM commission_withdrawal_requests
                WHERE user_id = ? AND status IN ({",".join("?" for _ in reserved_statuses)})
                """,
                (str(user_id), *reserved_statuses),
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

    def create_payout_binding_attempt(
        self,
        user_id: str,
        *,
        channel: str,
        state: str,
        expires_at: str,
        desktop_return_url: str = "",
        mobile_binding_url: str = "",
    ) -> PayoutBindingAttempt:
        now = _utc_now().isoformat()
        attempt_id = f"wpbind_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO payout_binding_attempts (
                        binding_attempt_id, user_id, provider, channel, state, status,
                        desktop_return_url, mobile_binding_url, qr_expires_at,
                        created_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        str(user_id),
                        PAYOUT_PROVIDER_WECHAT_PAY,
                        str(channel),
                        str(state),
                        BINDING_STATUS_CREATED,
                        str(desktop_return_url or ""),
                        str(mobile_binding_url or ""),
                        str(expires_at),
                        now,
                        str(expires_at),
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                    (attempt_id,),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("payout binding attempt")
                return self._row_to_binding_attempt(row)
            finally:
                conn.close()

    def update_payout_binding_attempt_urls(
        self,
        binding_attempt_id: str,
        *,
        desktop_return_url: str = "",
        mobile_binding_url: str = "",
    ) -> PayoutBindingAttempt:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE payout_binding_attempts
                    SET desktop_return_url = ?,
                        mobile_binding_url = ?
                    WHERE binding_attempt_id = ?
                    """,
                    (str(desktop_return_url or ""), str(mobile_binding_url or ""), str(binding_attempt_id)),
                )
                row = conn.execute(
                    "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                    (str(binding_attempt_id),),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("payout binding attempt")
                return self._row_to_binding_attempt(row)
            finally:
                conn.close()

    def mark_payout_binding_attempt_scanned(
        self,
        binding_attempt_id: str,
        *,
        state: str,
        scanned_at: str | None = None,
    ) -> PayoutBindingAttempt:
        scanned_text = str(scanned_at or _utc_now().isoformat())
        scanned_dt = _parse_dt(scanned_text)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                    (str(binding_attempt_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("payout binding attempt")
                attempt = self._row_to_binding_attempt(row)
                if attempt.state != str(state):
                    raise PreconditionFailure("payout binding state is invalid")
                if attempt.status in {BINDING_STATUS_BOUND, BINDING_STATUS_FAILED, BINDING_STATUS_CANCELED, BINDING_STATUS_EXPIRED}:
                    raise PreconditionFailure("payout binding attempt has already been consumed")
                if scanned_dt > _parse_dt(attempt.expires_at):
                    conn.execute(
                        """
                        UPDATE payout_binding_attempts
                        SET status = ?,
                            completed_at = ?,
                            failure_reason = ?
                        WHERE binding_attempt_id = ?
                        """,
                        (BINDING_STATUS_EXPIRED, scanned_dt.isoformat(), "binding attempt expired", attempt.binding_attempt_id),
                    )
                    conn.commit()
                    raise PreconditionFailure("payout binding attempt has expired")
                conn.execute(
                    """
                    UPDATE payout_binding_attempts
                    SET status = ?,
                        scanned_at = COALESCE(scanned_at, ?),
                        failure_reason = ''
                    WHERE binding_attempt_id = ?
                    """,
                    (BINDING_STATUS_SCANNED, scanned_dt.isoformat(), attempt.binding_attempt_id),
                )
                updated = conn.execute(
                    "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                    (attempt.binding_attempt_id,),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("payout binding attempt")
                return self._row_to_binding_attempt(updated)
            finally:
                conn.close()

    def get_payout_binding_attempt(self, binding_attempt_id: str) -> PayoutBindingAttempt | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                (str(binding_attempt_id),),
            ).fetchone()
            return None if row is None else self._row_to_binding_attempt(row)
        finally:
            conn.close()

    def get_latest_payout_binding_attempt(self, user_id: str) -> PayoutBindingAttempt | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM payout_binding_attempts
                WHERE user_id = ?
                ORDER BY created_at DESC, binding_attempt_id DESC
                LIMIT 1
                """,
                (str(user_id),),
            ).fetchone()
            return None if row is None else self._row_to_binding_attempt(row)
        finally:
            conn.close()

    def complete_payout_binding_attempt(
        self,
        user_id: str,
        *,
        binding_attempt_id: str,
        authorization_code: str,
        state: str,
        openid: str,
        appid: str,
        confirmed_learning_pyramid_user_id: str | None = None,
        completed_at: str | None = None,
    ) -> PayoutIdentity:
        normalized_openid = str(openid or "").strip()
        normalized_appid = str(appid or "").strip()
        if not normalized_openid:
            raise PreconditionFailure("wechat authorization did not return an OpenID")
        if not normalized_appid:
            raise PreconditionFailure("wechat payout appid is required")
        completed_text = str(completed_at or _utc_now().isoformat())
        completed_dt = _parse_dt(completed_text)
        identity_id = f"wpid_{uuid.uuid4().hex}"
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM payout_binding_attempts WHERE binding_attempt_id = ? LIMIT 1",
                    (str(binding_attempt_id),),
                ).fetchone()
                if row is None:
                    raise NotFound("payout binding attempt")
                attempt = self._row_to_binding_attempt(row)
                if attempt.user_id != str(user_id):
                    raise PreconditionFailure("payout binding attempt does not belong to the current user")
                if attempt.state != str(state):
                    raise PreconditionFailure("payout binding state is invalid")
                if attempt.status not in {
                    BINDING_STATUS_CREATED,
                    BINDING_STATUS_SCANNED,
                    BINDING_STATUS_AUTHORIZED,
                    BINDING_STATUS_CONFIRMED,
                }:
                    raise PreconditionFailure("payout binding attempt has already been consumed")
                confirmed_user = str(confirmed_learning_pyramid_user_id or "").strip()
                if confirmed_user and confirmed_user != attempt.user_id:
                    raise PreconditionFailure("confirmed account does not match payout binding attempt")
                if attempt.channel == "desktop_qr_official_account_h5":
                    if not confirmed_user:
                        raise PreconditionFailure("confirmed account is required for desktop QR payout binding")
                    if attempt.status == BINDING_STATUS_CREATED:
                        raise PreconditionFailure("payout binding attempt must be scanned before confirmation")
                if completed_dt > _parse_dt(attempt.expires_at):
                    conn.execute(
                        "UPDATE payout_binding_attempts SET status = ?, completed_at = ?, failure_reason = ? WHERE binding_attempt_id = ?",
                        (BINDING_STATUS_EXPIRED, completed_dt.isoformat(), "binding attempt expired", attempt.binding_attempt_id),
                    )
                    conn.commit()
                    raise PreconditionFailure("payout binding attempt has expired")
                conn.execute(
                    """
                    UPDATE payout_identities
                    SET status = ?, revoked_at = ?, updated_at = ?
                    WHERE user_id = ?
                      AND provider = ?
                      AND status = ?
                    """,
                    (
                        PAYOUT_IDENTITY_STATUS_REPLACED,
                        completed_dt.isoformat(),
                        completed_dt.isoformat(),
                        str(user_id),
                        PAYOUT_PROVIDER_WECHAT_PAY,
                        PAYOUT_IDENTITY_STATUS_ACTIVE,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO payout_identities (
                        identity_id, user_id, provider, appid, openid, masked_openid, status,
                        verified_at, latest_binding_attempt_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identity_id,
                        str(user_id),
                        PAYOUT_PROVIDER_WECHAT_PAY,
                        normalized_appid,
                        normalized_openid,
                        _mask_openid(normalized_openid),
                        PAYOUT_IDENTITY_STATUS_ACTIVE,
                        completed_dt.isoformat(),
                        attempt.binding_attempt_id,
                        completed_dt.isoformat(),
                        completed_dt.isoformat(),
                    ),
                )
                conn.execute(
                    """
                    UPDATE payout_binding_attempts
                    SET status = ?,
                        authorization_code_hash = ?,
                        resolved_openid = ?,
                        identity_id = ?,
                        authorized_at = COALESCE(authorized_at, ?),
                        confirmed_at = COALESCE(confirmed_at, ?),
                        completed_at = ?,
                        failure_reason = ''
                    WHERE binding_attempt_id = ?
                    """,
                    (
                        BINDING_STATUS_BOUND,
                        uuid.uuid5(uuid.NAMESPACE_URL, str(authorization_code or "")).hex if authorization_code else "",
                        normalized_openid,
                        identity_id,
                        completed_dt.isoformat(),
                        completed_dt.isoformat(),
                        completed_dt.isoformat(),
                        attempt.binding_attempt_id,
                    ),
                )
                updated = conn.execute("SELECT * FROM payout_identities WHERE identity_id = ? LIMIT 1", (identity_id,)).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("payout identity")
                return self._row_to_identity(updated)
            finally:
                conn.close()

    def get_active_payout_identity(self, user_id: str) -> PayoutIdentity | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM payout_identities
                WHERE user_id = ?
                  AND provider = ?
                  AND status = ?
                ORDER BY verified_at DESC, identity_id DESC
                LIMIT 1
                """,
                (str(user_id), PAYOUT_PROVIDER_WECHAT_PAY, PAYOUT_IDENTITY_STATUS_ACTIVE),
            ).fetchone()
            return None if row is None else self._row_to_identity(row)
        finally:
            conn.close()

    def get_payout_identity(self, identity_id: str) -> PayoutIdentity | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM payout_identities WHERE identity_id = ? LIMIT 1", (str(identity_id),)).fetchone()
            return None if row is None else self._row_to_identity(row)
        finally:
            conn.close()

    def list_admin_payout_identities(
        self,
        *,
        status: str | None = None,
        search_user_ids: set[str] | None = None,
        limit: int = 100,
    ) -> tuple[PayoutIdentity, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        where = []
        params: list[object] = []
        if status and str(status).strip().lower() != "all":
            where.append("status = ?")
            params.append(str(status).strip().lower())
        if search_user_ids is not None:
            if not search_user_ids:
                return tuple()
            placeholders = ",".join("?" for _ in search_user_ids)
            where.append(f"user_id IN ({placeholders})")
            params.extend(sorted(search_user_ids))
        params.append(normalized_limit)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM payout_identities
                {where_sql}
                ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, updated_at DESC, identity_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_identity(row) for row in rows)
        finally:
            conn.close()

    def create_withdrawal_request(
        self,
        user_id: str,
        *,
        amount_cent: int,
        identity_id: str | None = None,
        wechat_open_id: str | None = None,
    ) -> WithdrawalRequest:
        normalized_amount = int(amount_cent)
        if normalized_amount <= 0:
            raise PreconditionFailure("withdrawal amount must be positive")
        identity = self.get_payout_identity(identity_id) if identity_id else self.get_active_payout_identity(user_id)
        normalized_open_id = str(wechat_open_id or "").strip()
        if identity is None:
            if normalized_open_id and str(os.getenv("PLM_ENABLE_MANUAL_TEST_PAYMENT") or "").lower() in {"1", "true", "yes", "on"}:
                identity = PayoutIdentity(
                    identity_id="",
                    user_id=str(user_id),
                    provider=PAYOUT_PROVIDER_WECHAT_PAY,
                    appid=str(os.getenv("PLM_WECHAT_PAY_APP_ID") or "manual_test"),
                    openid=normalized_open_id,
                    masked_openid=_mask_openid(normalized_open_id),
                    status=PAYOUT_IDENTITY_STATUS_ACTIVE,
                    verified_at=_utc_now().isoformat(),
                    revoked_at=None,
                    latest_binding_attempt_id=None,
                    failure_reason="",
                    created_at=_utc_now().isoformat(),
                    updated_at=_utc_now().isoformat(),
                )
            else:
                raise PreconditionFailure("wechat receiving identity is required")
        if identity.user_id != str(user_id) or identity.status != PAYOUT_IDENTITY_STATUS_ACTIVE:
            raise PreconditionFailure("wechat receiving identity is required")
        account = self.get_user_account(user_id)
        if normalized_amount > account.withdrawable_cent:
            raise PreconditionFailure("withdrawal amount exceeds withdrawable commission balance")
        withdrawal_id = f"mwd_{uuid.uuid4().hex}"
        out_bill_no = _new_out_bill_no()
        created_at = _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                account_locked = self.get_user_account(user_id)
                if normalized_amount > account_locked.withdrawable_cent:
                    raise PreconditionFailure("withdrawal amount exceeds withdrawable commission balance")
                conn.execute(
                    """
                    INSERT INTO commission_withdrawal_requests (
                        withdrawal_id, user_id, amount_cent, target_type, wechat_open_id, status,
                        created_at, identity_id, identity_masked_label, out_bill_no, reserved_at
                    )
                    VALUES (?, ?, ?, 'wechat_pay', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        withdrawal_id,
                        str(user_id),
                        normalized_amount,
                        identity.openid,
                        WITHDRAWAL_STATUS_CREATED,
                        created_at,
                        identity.identity_id or None,
                        identity.masked_openid,
                        out_bill_no,
                        created_at,
                    ),
                )
                row = conn.execute("SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1", (withdrawal_id,)).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("withdrawal request")
                return self._row_to_withdrawal(row)
            finally:
                conn.close()

    def append_payout_provider_event(
        self,
        withdrawal_id: str,
        *,
        event_type: str,
        provider: str = PAYOUT_PROVIDER_WECHAT_PAY,
        provider_event_id: str = "",
        out_bill_no: str = "",
        transfer_bill_no: str | None = None,
        provider_state: str = "",
        mapped_status: str = "",
        raw_payload_json: str = "",
        signature_verified: bool = False,
        created_at: str | None = None,
    ) -> PayoutProviderEvent:
        event_id = f"wpevt_{uuid.uuid4().hex}"
        now_text = str(created_at or _utc_now().isoformat())
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO payout_provider_events (
                        event_id, withdrawal_id, event_type, provider, provider_event_id, out_bill_no,
                        transfer_bill_no, provider_state, mapped_status, raw_payload_json,
                        signature_verified, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        str(withdrawal_id),
                        str(event_type),
                        str(provider),
                        str(provider_event_id or ""),
                        str(out_bill_no or ""),
                        None if transfer_bill_no is None else str(transfer_bill_no),
                        str(provider_state or ""),
                        str(mapped_status or ""),
                        str(raw_payload_json or ""),
                        1 if signature_verified else 0,
                        now_text,
                    ),
                )
                row = conn.execute("SELECT * FROM payout_provider_events WHERE event_id = ? LIMIT 1", (event_id,)).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("payout provider event")
                return self._row_to_provider_event(row)
            finally:
                conn.close()

    def list_payout_provider_events(
        self,
        *,
        withdrawal_id: str | None = None,
        limit: int = 100,
    ) -> tuple[PayoutProviderEvent, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=500)
        where = ""
        params: list[object] = []
        if withdrawal_id:
            where = "WHERE withdrawal_id = ?"
            params.append(str(withdrawal_id))
        params.append(normalized_limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM payout_provider_events
                {where}
                ORDER BY created_at ASC, event_id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_provider_event(row) for row in rows)
        finally:
            conn.close()

    def _update_withdrawal_status(
        self,
        withdrawal_id: str,
        *,
        status: str,
        provider_transfer_no: str | None = None,
        transfer_bill_no: str | None = None,
        provider_state: str = "",
        package_info: str | None = None,
        failure_reason: str = "",
        raw_payload_json: str = "",
    ) -> WithdrawalRequest:
        now_text = _utc_now().isoformat()
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
                if current.status in {WITHDRAWAL_STATUS_SUCCEEDED, WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED}:
                    return current
                completed_at = now_text if status in {WITHDRAWAL_STATUS_SUCCEEDED, WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED} else None
                submitted_at = now_text if current.submitted_at is None else current.submitted_at
                confirmation_requested_at = now_text if status == WITHDRAWAL_STATUS_AWAITING_CONFIRMATION else current.confirmation_requested_at
                conn.execute(
                    """
                    UPDATE commission_withdrawal_requests
                    SET status = ?,
                        provider_transfer_no = COALESCE(?, provider_transfer_no),
                        transfer_bill_no = COALESCE(?, transfer_bill_no),
                        provider_state = ?,
                        package_info = COALESCE(?, package_info),
                        submitted_at = ?,
                        completed_at = COALESCE(?, completed_at),
                        confirmation_requested_at = ?,
                        failure_reason = ?
                    WHERE withdrawal_id = ?
                    """,
                    (
                        status,
                        str(provider_transfer_no or transfer_bill_no or "") or None,
                        str(transfer_bill_no or provider_transfer_no or "") or None,
                        str(provider_state or current.provider_state or ""),
                        None if package_info is None else str(package_info),
                        submitted_at,
                        completed_at,
                        confirmation_requested_at,
                        "" if status not in {WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED, WITHDRAWAL_STATUS_NEEDS_ATTENTION} else str(failure_reason or ""),
                        str(withdrawal_id),
                    ),
                )
                updated = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("withdrawal request")
                result = self._row_to_withdrawal(updated)
                conn.execute(
                    """
                    INSERT INTO payout_provider_events (
                        event_id, withdrawal_id, event_type, provider, provider_event_id, out_bill_no,
                        transfer_bill_no, provider_state, mapped_status, raw_payload_json,
                        signature_verified, created_at
                    )
                    VALUES (?, ?, 'create_response', ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        f"wpevt_{uuid.uuid4().hex}",
                        result.withdrawal_id,
                        PAYOUT_PROVIDER_WECHAT_PAY,
                        result.transfer_bill_no or result.provider_transfer_no or "",
                        result.out_bill_no,
                        result.transfer_bill_no,
                        str(provider_state or ""),
                        status,
                        str(raw_payload_json or ""),
                        now_text,
                    ),
                )
                conn.commit()
                return result
            finally:
                conn.close()

    def mark_withdrawal_awaiting_confirmation(
        self,
        withdrawal_id: str,
        *,
        transfer_bill_no: str | None,
        provider_state: str,
        package_info: str,
        raw_payload_json: str = "",
    ) -> WithdrawalRequest:
        return self._update_withdrawal_status(
            withdrawal_id,
            status=WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
            transfer_bill_no=transfer_bill_no,
            provider_state=provider_state,
            package_info=package_info,
            raw_payload_json=raw_payload_json,
        )

    def mark_withdrawal_processing(
        self,
        withdrawal_id: str,
        *,
        provider_transfer_no: str | None = None,
        provider_state: str = "PROCESSING",
        raw_payload_json: str = "",
    ) -> WithdrawalRequest:
        return self._update_withdrawal_status(
            withdrawal_id,
            status=WITHDRAWAL_STATUS_PROCESSING,
            provider_transfer_no=provider_transfer_no,
            provider_state=provider_state,
            raw_payload_json=raw_payload_json,
        )

    def mark_withdrawal_succeeded(
        self,
        withdrawal_id: str,
        *,
        provider_transfer_no: str | None = None,
        completed_at: str | None = None,
    ) -> WithdrawalRequest:
        del completed_at
        return self._update_withdrawal_status(
            withdrawal_id,
            status=WITHDRAWAL_STATUS_SUCCEEDED,
            provider_transfer_no=provider_transfer_no,
            provider_state="SUCCESS",
        )

    def mark_withdrawal_failed(
        self,
        withdrawal_id: str,
        *,
        failure_reason: str,
        provider_transfer_no: str | None = None,
        completed_at: str | None = None,
    ) -> WithdrawalRequest:
        del completed_at
        return self._update_withdrawal_status(
            withdrawal_id,
            status=WITHDRAWAL_STATUS_FAILED,
            provider_transfer_no=provider_transfer_no,
            provider_state="FAIL",
            failure_reason=failure_reason,
        )

    def apply_withdrawal_provider_result(
        self,
        *,
        out_bill_no: str,
        provider_state: str,
        mapped_status: str,
        transfer_bill_no: str | None,
        amount_cent: int | None,
        appid: str | None,
        raw_payload_json: str,
        provider_event_id: str,
        event_type: str,
        failure_reason: str = "",
        signature_verified: bool = True,
    ) -> WithdrawalRequest:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE out_bill_no = ? LIMIT 1",
                    (str(out_bill_no),),
                ).fetchone()
                if row is None:
                    raise NotFound("withdrawal request")
                current = self._row_to_withdrawal(row)
                if amount_cent is not None and int(amount_cent) != current.amount_cent:
                    self._create_reconciliation_warning_locked(
                        conn,
                        current.withdrawal_id,
                        severity="critical",
                        reason_code="amount_mismatch",
                        message="provider transfer amount does not match local withdrawal amount",
                    )
                    mapped_status = WITHDRAWAL_STATUS_NEEDS_ATTENTION
                    failure_reason = "provider transfer amount mismatch"
                if appid and current.identity_id:
                    identity = conn.execute("SELECT * FROM payout_identities WHERE identity_id = ? LIMIT 1", (current.identity_id,)).fetchone()
                    if identity is not None and str(identity["appid"]) != str(appid):
                        self._create_reconciliation_warning_locked(
                            conn,
                            current.withdrawal_id,
                            severity="critical",
                            reason_code="identity_mismatch",
                            message="provider transfer appid does not match bound payout identity",
                        )
                        mapped_status = WITHDRAWAL_STATUS_NEEDS_ATTENTION
                        failure_reason = "provider transfer identity mismatch"
                now_text = _utc_now().isoformat()
                duplicate_event = None
                if provider_event_id:
                    duplicate_event = conn.execute(
                        """
                        SELECT event_id
                        FROM payout_provider_events
                        WHERE withdrawal_id = ?
                          AND event_type = ?
                          AND provider_event_id = ?
                        LIMIT 1
                        """,
                        (current.withdrawal_id, str(event_type), str(provider_event_id)),
                    ).fetchone()
                if duplicate_event is None:
                    event_id = f"wpevt_{uuid.uuid4().hex}"
                    conn.execute(
                        """
                        INSERT INTO payout_provider_events (
                            event_id, withdrawal_id, event_type, provider, provider_event_id, out_bill_no,
                            transfer_bill_no, provider_state, mapped_status, raw_payload_json,
                            signature_verified, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            current.withdrawal_id,
                            str(event_type),
                            PAYOUT_PROVIDER_WECHAT_PAY,
                            str(provider_event_id or ""),
                            current.out_bill_no,
                            None if transfer_bill_no is None else str(transfer_bill_no),
                            str(provider_state or ""),
                            str(mapped_status or ""),
                            str(raw_payload_json or ""),
                            1 if signature_verified else 0,
                            now_text,
                        ),
                    )
                if current.status in {WITHDRAWAL_STATUS_SUCCEEDED, WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED}:
                    conn.commit()
                    return current
                terminal = mapped_status in {
                    WITHDRAWAL_STATUS_SUCCEEDED,
                    WITHDRAWAL_STATUS_FAILED,
                    WITHDRAWAL_STATUS_CANCELED,
                    WITHDRAWAL_STATUS_NEEDS_ATTENTION,
                }
                conn.execute(
                    """
                    UPDATE commission_withdrawal_requests
                    SET status = ?,
                        provider_transfer_no = COALESCE(?, provider_transfer_no),
                        transfer_bill_no = COALESCE(?, transfer_bill_no),
                        provider_state = ?,
                        completed_at = CASE WHEN ? THEN ? ELSE completed_at END,
                        failure_reason = ?
                    WHERE withdrawal_id = ?
                    """,
                    (
                        mapped_status,
                        str(transfer_bill_no or "") or None,
                        str(transfer_bill_no or "") or None,
                        str(provider_state or ""),
                        1 if terminal else 0,
                        now_text,
                        str(failure_reason or "") if mapped_status != WITHDRAWAL_STATUS_SUCCEEDED else "",
                        current.withdrawal_id,
                    ),
                )
                updated = conn.execute(
                    "SELECT * FROM commission_withdrawal_requests WHERE withdrawal_id = ? LIMIT 1",
                    (current.withdrawal_id,),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("withdrawal request")
                return self._row_to_withdrawal(updated)
            finally:
                conn.close()

    def _create_reconciliation_warning_locked(
        self,
        conn: sqlite3.Connection,
        withdrawal_id: str,
        *,
        severity: str,
        reason_code: str,
        message: str,
    ) -> None:
        warning_id = f"warn_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO reconciliation_warnings (
                warning_id, withdrawal_id, severity, reason_code, message, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'open', ?)
            """,
            (warning_id, str(withdrawal_id), str(severity), str(reason_code), str(message), _utc_now().isoformat()),
        )

    def create_reconciliation_warning(
        self,
        withdrawal_id: str,
        *,
        severity: str,
        reason_code: str,
        message: str,
    ) -> ReconciliationWarning:
        with self._lock:
            conn = self._connect()
            try:
                self._create_reconciliation_warning_locked(
                    conn,
                    withdrawal_id,
                    severity=severity,
                    reason_code=reason_code,
                    message=message,
                )
                row = conn.execute(
                    "SELECT * FROM reconciliation_warnings WHERE withdrawal_id = ? ORDER BY created_at DESC LIMIT 1",
                    (str(withdrawal_id),),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("reconciliation warning")
                return self._row_to_warning(row)
            finally:
                conn.close()

    def list_reconciliation_warnings(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> tuple[ReconciliationWarning, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=500)
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
                FROM reconciliation_warnings
                {where}
                ORDER BY created_at DESC, warning_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_warning(row) for row in rows)
        finally:
            conn.close()

    def resolve_reconciliation_warning(self, warning_id: str, *, resolved_at: str | None = None) -> ReconciliationWarning:
        normalized_warning_id = str(warning_id or "").strip()
        if not normalized_warning_id:
            raise PreconditionFailure("reconciliation warning id must be non-empty")
        resolved_at_text = resolved_at or _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM reconciliation_warnings WHERE warning_id = ? LIMIT 1",
                    (normalized_warning_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("reconciliation warning")
                conn.execute(
                    """
                    UPDATE reconciliation_warnings
                    SET status = 'resolved',
                        resolved_at = COALESCE(resolved_at, ?)
                    WHERE warning_id = ?
                    """,
                    (resolved_at_text, normalized_warning_id),
                )
                updated = conn.execute(
                    "SELECT * FROM reconciliation_warnings WHERE warning_id = ? LIMIT 1",
                    (normalized_warning_id,),
                ).fetchone()
                conn.commit()
                if updated is None:
                    raise NotFound("reconciliation warning")
                return self._row_to_warning(updated)
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

    def list_withdrawals_for_reconciliation(
        self,
        *,
        min_age_minutes: int,
        limit: int,
        now: datetime | None = None,
    ) -> tuple[WithdrawalRequest, ...]:
        normalized_min_age = max(0, int(min_age_minutes))
        cutoff = (now or _utc_now()) - timedelta(minutes=normalized_min_age)
        statuses = (WITHDRAWAL_STATUS_AWAITING_CONFIRMATION, WITHDRAWAL_STATUS_PROCESSING)
        normalized_limit = _normalize_limit(limit, default=100, maximum=500)
        conn = self._connect()
        try:
            if normalized_min_age <= 0:
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM commission_withdrawal_requests
                    WHERE status IN ({",".join("?" for _ in statuses)})
                    ORDER BY COALESCE(submitted_at, created_at) ASC, withdrawal_id ASC
                    LIMIT ?
                    """,
                    (*statuses, normalized_limit),
                ).fetchall()
                return tuple(self._row_to_withdrawal(row) for row in rows)
            rows = conn.execute(
                f"""
                SELECT *
                FROM commission_withdrawal_requests
                WHERE status IN ({",".join("?" for _ in statuses)})
                  AND COALESCE(submitted_at, created_at) <= ?
                ORDER BY COALESCE(submitted_at, created_at) ASC, withdrawal_id ASC
                LIMIT ?
                """,
                (*statuses, cutoff.isoformat(), normalized_limit),
            ).fetchall()
            return tuple(self._row_to_withdrawal(row) for row in rows)
        finally:
            conn.close()

    def record_reconciliation_run(
        self,
        *,
        run_id: str,
        run_type: str,
        started_at: str,
        finished_at: str,
        limit: int,
        scanned_count: int,
        settled_count: int = 0,
        canceled_count: int = 0,
        succeeded_count: int = 0,
        failed_count: int = 0,
        needs_attention_count: int = 0,
        error_count: int = 0,
        summary_json: str = "",
    ) -> ReconciliationRun:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO reconciliation_runs (
                        run_id, run_type, started_at, finished_at, limit_count, scanned_count,
                        settled_count, canceled_count, succeeded_count, failed_count,
                        needs_attention_count, error_count, summary_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(run_id),
                        str(run_type),
                        str(started_at),
                        str(finished_at),
                        int(limit),
                        int(scanned_count),
                        int(settled_count),
                        int(canceled_count),
                        int(succeeded_count),
                        int(failed_count),
                        int(needs_attention_count),
                        int(error_count),
                        str(summary_json or ""),
                    ),
                )
                row = conn.execute("SELECT * FROM reconciliation_runs WHERE run_id = ? LIMIT 1", (str(run_id),)).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("reconciliation run")
                return self._row_to_run(row)
            finally:
                conn.close()

    def list_reconciliation_runs(self, *, run_type: str | None = None, limit: int = 100) -> tuple[ReconciliationRun, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=500)
        where = ""
        params: list[object] = []
        if run_type:
            where = "WHERE run_type = ?"
            params.append(str(run_type))
        params.append(normalized_limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM reconciliation_runs
                {where}
                ORDER BY started_at DESC, run_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_run(row) for row in rows)
        finally:
            conn.close()

    def get_admin_overview(self) -> CommissionAdminOverview:
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
            reserved_statuses = (
                WITHDRAWAL_STATUS_CREATED,
                WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
                WITHDRAWAL_STATUS_PROCESSING,
            )
            reserved = conn.execute(
                f"""
                SELECT COALESCE(SUM(amount_cent), 0) AS total
                FROM commission_withdrawal_requests
                WHERE status IN ({",".join("?" for _ in reserved_statuses)})
                """,
                reserved_statuses,
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
