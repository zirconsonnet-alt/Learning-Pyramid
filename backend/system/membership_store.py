import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.models.errors import NotFound, PreconditionFailure
from backend.system.app_paths import resolve_membership_db_path
from backend.system.membership_marketing_store import (
    COUPON_STATUS_AVAILABLE,
    COUPON_STATUS_EXPIRED,
    COUPON_STATUS_REVOKED,
    COUPON_STATUS_USED,
    INVITE_BINDING_STATUS_COMMISSION_PENDING,
    INVITE_BINDING_STATUS_BOUND,
    INVITE_BINDING_STATUS_REWARDED,
    INVITE_REWARD_COUPON_AMOUNT_CENT,
    INVITE_REWARD_COUPON_EXPIRE_DAYS,
    INVITE_REWARD_COUPON_MIN_SPEND_CENT,
    INVITE_REWARD_SOURCE,
    INVITE_REWARD_COUPON_TITLE,
    REWARD_STATUS_ISSUED,
    REWARD_STATUS_REVOKED,
)
from backend.system.membership_commission_store import MembershipCommissionStore, commission_refund_window_minutes
from backend.system.membership_payment_service import (
    MembershipRemotePaymentStatus,
    PAYMENT_PROVIDER_MANUAL_TEST,
    list_supported_membership_payment_providers,
)

BASE_MONTHLY_PRICE_CENT = 2000
FIRST_ORDER_DISCOUNT_CENT = 0
FIRST_ORDER_PRICE_CENT = BASE_MONTHLY_PRICE_CENT - FIRST_ORDER_DISCOUNT_CENT
RENEWAL_PRICE_CENT = BASE_MONTHLY_PRICE_CENT
MEMBERSHIP_PRICING_VERSION = "membership_plans_v2"
MEMBERSHIP_PERIOD_DAYS = 30
MEMBERSHIP_PLAN_MONTHLY = "monthly"
MEMBERSHIP_PLAN_GRADUATE_EXAM = "graduate_exam"
MEMBERSHIP_PLAN_NAMES = {
    MEMBERSHIP_PLAN_MONTHLY: "月会员",
    MEMBERSHIP_PLAN_GRADUATE_EXAM: "考研套餐",
}
GRADUATE_EXAM_DAILY_PRICE_CENT = 50
GRADUATE_EXAM_CUTOFF_MONTH = 11
GRADUATE_EXAM_CUTOFF_DAY = 21
GRADUATE_EXAM_END_MONTH = 12
GRADUATE_EXAM_END_DAY = 21
CHINA_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
ORDER_TTL_MINUTES = 30
REFUND_WINDOW_HOURS = 24
REFUND_WINDOW_ENV = "LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES"
REFUND_WINDOW_EXPIRED_MESSAGE = "Membership refund period has expired."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_limit(limit: int, *, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


def membership_refund_window_minutes() -> int:
    raw = str(os.getenv(REFUND_WINDOW_ENV) or "").strip()
    if not raw:
        return REFUND_WINDOW_HOURS * 60
    try:
        value = int(raw)
    except Exception:
        return REFUND_WINDOW_HOURS * 60
    return max(1, min(value, 30 * 24 * 60))


def _normalize_provider(provider: str) -> str:
    value = str(provider).strip().lower()
    supported_providers = set(list_supported_membership_payment_providers())
    if not supported_providers:
        raise PreconditionFailure("membership payments are unavailable in this deployment")
    if value not in supported_providers:
        supported_text = ", ".join(sorted(supported_providers))
        raise PreconditionFailure(f"membership payment provider must be one of: {supported_text}")
    return value


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_membership_plan_id(plan_id: str | None) -> str:
    value = str(plan_id or "").strip().lower()
    if not value:
        return MEMBERSHIP_PLAN_MONTHLY
    if value not in MEMBERSHIP_PLAN_NAMES:
        supported_text = ", ".join(MEMBERSHIP_PLAN_NAMES)
        raise PreconditionFailure(f"membership planId must be one of: {supported_text}")
    return value


def _membership_plan_name(plan_id: str | None) -> str:
    normalized_plan_id = _normalize_membership_plan_id(plan_id)
    return MEMBERSHIP_PLAN_NAMES[normalized_plan_id]


def _graduate_exam_plan_days_and_amount(now: datetime) -> tuple[int, int]:
    purchase_date = now.astimezone(CHINA_TIMEZONE).date()
    cutoff_date = date(purchase_date.year, GRADUATE_EXAM_CUTOFF_MONTH, GRADUATE_EXAM_CUTOFF_DAY)
    if purchase_date >= cutoff_date:
        raise PreconditionFailure("考研套餐仅支持在11月21日前购买")
    end_date = date(purchase_date.year, GRADUATE_EXAM_END_MONTH, GRADUATE_EXAM_END_DAY)
    period_days = (end_date - purchase_date).days + 1
    if period_days <= 0:
        raise PreconditionFailure("考研套餐当前不可购买")
    return period_days, period_days * GRADUATE_EXAM_DAILY_PRICE_CENT


@dataclass(frozen=True, slots=True)
class MembershipSummary:
    user_id: str
    current_status: str
    current_starts_at: str | None
    current_ends_at: str | None
    is_active: bool
    is_first_order_eligible: bool
    base_monthly_price_cent: int
    first_order_price_cent: int
    renewal_price_cent: int
    current_price_cent: int
    supported_payment_providers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MembershipOrderPreview:
    user_id: str
    plan_id: str
    plan_name: str
    order_type: str
    period_days: int
    list_amount_cent: int
    first_order_discount_cent: int
    coupon_discount_cent: int
    payable_amount_cent: int
    coupon_id: str | None


@dataclass(frozen=True, slots=True)
class MembershipOrder:
    order_id: str
    user_id: str
    plan_id: str
    plan_name: str
    order_type: str
    pricing_version: str
    period_days: int
    list_amount_cent: int
    first_order_discount_cent: int
    coupon_discount_cent: int
    payable_amount_cent: int
    coupon_id: str | None
    provider: str
    provider_trade_no: str | None
    status: str
    client_ip: str
    client_version: str
    created_at: str
    paid_at: str | None
    closed_at: str | None
    refunded_at: str | None
    expired_at: str | None
    entitlement_id: str | None
    remark: str


@dataclass(frozen=True, slots=True)
class MembershipCreateOrderResult:
    order: MembershipOrder
    reused_existing_order: bool


@dataclass(frozen=True, slots=True)
class MembershipPaymentConfirmation:
    order: MembershipOrder
    membership: MembershipSummary
    payment_id: str
    idempotent: bool


@dataclass(frozen=True, slots=True)
class MembershipOrderCloseResult:
    order: MembershipOrder
    membership: MembershipSummary
    idempotent: bool


@dataclass(frozen=True, slots=True)
class MembershipPaymentSyncResult:
    order: MembershipOrder
    membership: MembershipSummary
    payment_id: str | None
    confirmed: bool
    idempotent: bool


@dataclass(frozen=True, slots=True)
class MembershipPaymentRecord:
    payment_id: str
    order_id: str
    provider: str
    provider_trade_no: str
    provider_buyer_id: str
    amount_cent: int
    status: str
    callback_payload_json: str
    created_at: str
    confirmed_at: str | None
    refund_out_refund_no: str | None
    refund_callback_payload_json: str
    refund_requested_at: str | None
    refunded_at: str | None


@dataclass(frozen=True, slots=True)
class MembershipRefundResult:
    order: MembershipOrder
    membership: MembershipSummary
    idempotent: bool
    restored_coupon_id: str | None
    restored_coupon_status: str | None
    revoked_reward_coupon_id: str | None
    completed: bool
    refund_request_submitted: bool
    remote_status: str | None
    provider_refund_no: str | None


@dataclass(frozen=True, slots=True)
class MembershipGrantResult:
    user_id: str
    entitlement_id: str
    source_ref_id: str
    months: int
    granted_days: int
    start_at: str
    end_at: str
    membership: MembershipSummary


@dataclass(frozen=True, slots=True)
class MembershipAdminOverview:
    paid_order_count: int
    active_membership_count: int
    total_paid_amount_cent: int
    first_purchase_paid_count: int
    renewal_paid_count: int
    pending_order_count: int


class MembershipStore:
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
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (str(table_name),),
        ).fetchone()
        return row is not None

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table_name: str) -> dict[str, sqlite3.Row]:
        return {str(row["name"]): row for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}

    @staticmethod
    def _validate_table_columns(
        conn: sqlite3.Connection,
        table_name: str,
        required_columns: set[str],
    ) -> dict[str, sqlite3.Row]:
        columns = MembershipStore._table_columns(conn, table_name)
        missing = sorted(required_columns - set(columns))
        if missing:
            raise RuntimeError(f"{table_name} schema is not current; missing columns: {', '.join(missing)}")
        return columns

    @classmethod
    def _validate_current_schema(cls, conn: sqlite3.Connection) -> None:
        cls._validate_table_columns(
            conn,
            "membership_orders",
            {
                "order_id",
                "user_id",
                "plan_id",
                "order_type",
                "pricing_version",
                "period_days",
                "list_amount_cent",
                "first_order_discount_cent",
                "coupon_discount_cent",
                "payable_amount_cent",
                "coupon_id",
                "provider",
                "status",
                "provider_trade_no",
                "client_ip",
                "client_version",
                "created_at",
                "paid_at",
                "closed_at",
                "refunded_at",
                "expired_at",
                "entitlement_id",
                "remark",
            },
        )
        cls._validate_table_columns(
            conn,
            "membership_payments",
            {
                "payment_id",
                "order_id",
                "provider",
                "provider_trade_no",
                "provider_buyer_id",
                "amount_cent",
                "status",
                "callback_payload_json",
                "created_at",
                "confirmed_at",
                "refund_out_refund_no",
                "refund_callback_payload_json",
                "refund_requested_at",
                "refunded_at",
            },
        )
        entitlement_columns = cls._validate_table_columns(
            conn,
            "membership_entitlements",
            {
                "entitlement_id",
                "user_id",
                "source_order_id",
                "source_kind",
                "start_at",
                "end_at",
                "granted_days",
                "status",
                "granted_at",
                "revoked_at",
                "revoke_reason",
            },
        )
        source_order = entitlement_columns["source_order_id"]
        if int(source_order["notnull"] or 0) != 0:
            raise RuntimeError("membership_entitlements schema is not current; source_order_id must be nullable")

    @classmethod
    def _validate_existing_current_schema(cls, conn: sqlite3.Connection) -> None:
        for table_name in ("membership_orders", "membership_payments", "membership_entitlements"):
            if cls._table_exists(conn, table_name):
                cls._validate_current_schema(conn)
                return

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                self._validate_existing_current_schema(conn)
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS membership_orders (
                        order_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        plan_id TEXT NOT NULL DEFAULT 'monthly',
                        order_type TEXT NOT NULL,
                        pricing_version TEXT NOT NULL,
                        period_days INTEGER NOT NULL,
                        list_amount_cent INTEGER NOT NULL,
                        first_order_discount_cent INTEGER NOT NULL DEFAULT 0,
                        coupon_discount_cent INTEGER NOT NULL DEFAULT 0,
                        payable_amount_cent INTEGER NOT NULL,
                        coupon_id TEXT,
                        provider TEXT NOT NULL,
                        status TEXT NOT NULL,
                        provider_trade_no TEXT,
                        client_ip TEXT NOT NULL DEFAULT '',
                        client_version TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        paid_at TEXT,
                        closed_at TEXT,
                        refunded_at TEXT,
                        expired_at TEXT,
                        entitlement_id TEXT,
                        remark TEXT NOT NULL DEFAULT '',
                        CHECK (order_type IN ('first_purchase', 'renewal')),
                        CHECK (period_days > 0),
                        CHECK (list_amount_cent >= 0),
                        CHECK (first_order_discount_cent >= 0),
                        CHECK (coupon_discount_cent >= 0),
                        CHECK (payable_amount_cent >= 0),
                        CHECK (status IN ('pending', 'paid', 'closed', 'expired', 'refund_pending', 'refunded'))
                    );

                    CREATE TABLE IF NOT EXISTS membership_payments (
                        payment_id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        provider_trade_no TEXT NOT NULL,
                        provider_buyer_id TEXT NOT NULL DEFAULT '',
                        amount_cent INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        callback_payload_json TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        confirmed_at TEXT,
                        refund_out_refund_no TEXT,
                        refund_callback_payload_json TEXT NOT NULL DEFAULT '',
                        refund_requested_at TEXT,
                        refunded_at TEXT,
                        CHECK (amount_cent >= 0),
                        CHECK (status IN ('initiated', 'succeeded', 'refund_pending', 'refunded', 'failed'))
                    );

                    CREATE TABLE IF NOT EXISTS membership_entitlements (
                        entitlement_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        source_order_id TEXT,
                        source_kind TEXT NOT NULL DEFAULT 'order',
                        start_at TEXT NOT NULL,
                        end_at TEXT NOT NULL,
                        granted_days INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        granted_at TEXT NOT NULL,
                        revoked_at TEXT,
                        revoke_reason TEXT NOT NULL DEFAULT '',
                        CHECK (granted_days > 0),
                        CHECK (status IN ('active', 'expired', 'revoked'))
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_orders_provider_trade_no
                    ON membership_orders (provider, provider_trade_no)
                    WHERE provider_trade_no IS NOT NULL;

                    CREATE INDEX IF NOT EXISTS idx_membership_orders_user_created
                    ON membership_orders (user_id, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_membership_orders_user_status
                    ON membership_orders (user_id, status, created_at DESC);

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_payments_trade_no
                    ON membership_payments (provider, provider_trade_no);

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_payments_refund_out_refund_no
                    ON membership_payments (provider, refund_out_refund_no)
                    WHERE refund_out_refund_no IS NOT NULL;

                    CREATE INDEX IF NOT EXISTS idx_membership_payments_order
                    ON membership_payments (order_id, created_at DESC);

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_entitlements_source_order
                    ON membership_entitlements (source_order_id);

                    CREATE INDEX IF NOT EXISTS idx_membership_entitlements_user_end
                    ON membership_entitlements (user_id, end_at DESC);
                    """
                )
                self._validate_current_schema(conn)
                conn.commit()
            finally:
                conn.close()

    def healthcheck(self) -> dict[str, object]:
        conn = self._connect()
        try:
            conn.execute("SELECT 1").fetchone()
            return {"ok": True, "dbPath": str(self.db_path)}
        finally:
            conn.close()

    def _sync_expired_rows(self, conn: sqlite3.Connection, *, user_id: str | None = None, now: datetime | None = None) -> None:
        now_text = (now or _utc_now()).isoformat()
        order_params: list[object] = [now_text]
        order_filter = ""
        if user_id:
            order_filter = " AND user_id = ?"
            order_params.append(str(user_id))
        conn.execute(
            f"""
            UPDATE membership_orders
            SET status = 'expired'
            WHERE status = 'pending'
              AND expired_at IS NOT NULL
              AND expired_at <= ?{order_filter}
            """,
            tuple(order_params),
        )
        entitlement_params: list[object] = [now_text]
        entitlement_filter = ""
        if user_id:
            entitlement_filter = " AND user_id = ?"
            entitlement_params.append(str(user_id))
        conn.execute(
            f"""
            UPDATE membership_entitlements
            SET status = 'expired'
            WHERE status = 'active'
              AND end_at <= ?{entitlement_filter}
            """,
            tuple(entitlement_params),
        )
        if self._table_exists(conn, "coupons"):
            coupon_params: list[object] = [now_text]
            coupon_filter = ""
            if user_id:
                coupon_filter = " AND user_id = ?"
                coupon_params.append(str(user_id))
            conn.execute(
                f"""
                UPDATE coupons
                SET status = '{COUPON_STATUS_EXPIRED}'
                WHERE status = '{COUPON_STATUS_AVAILABLE}'
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?{coupon_filter}
                """,
                tuple(coupon_params),
            )

    def _ensure_commission_tables(self, conn: sqlite3.Connection) -> None:
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
                completed_at TEXT
            );
            """
        )

    @staticmethod
    def _ensure_refund_window_open(order: MembershipOrder, *, now: datetime) -> None:
        if order.status != "paid":
            return
        if not order.paid_at:
            raise PreconditionFailure("membership order successful payment time is unavailable")
        paid_at = _parse_dt(order.paid_at)
        if now > paid_at + timedelta(minutes=membership_refund_window_minutes()):
            raise PreconditionFailure(REFUND_WINDOW_EXPIRED_MESSAGE)

    def ensure_refund_can_start(self, order: MembershipOrder, *, now: datetime | None = None) -> None:
        self._ensure_refund_window_open(order, now=now or _utc_now())

    def _is_first_order_eligible(self, conn: sqlite3.Connection, user_id: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM membership_orders WHERE user_id = ? AND status = 'paid' LIMIT 1",
            (str(user_id),),
        ).fetchone()
        return row is None

    def _preview_for_user(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        *,
        plan_id: str | None = None,
        coupon_discount_cent: int = 0,
        coupon_id: str | None = None,
        now: datetime | None = None,
    ) -> MembershipOrderPreview:
        is_first = self._is_first_order_eligible(conn, user_id)
        normalized_plan_id = _normalize_membership_plan_id(plan_id)
        if normalized_plan_id == MEMBERSHIP_PLAN_GRADUATE_EXAM:
            period_days, list_amount_cent = _graduate_exam_plan_days_and_amount(now or _utc_now())
        else:
            period_days = MEMBERSHIP_PERIOD_DAYS
            list_amount_cent = BASE_MONTHLY_PRICE_CENT
        first_order_discount_cent = 0
        normalized_coupon_discount_cent = max(0, int(coupon_discount_cent))
        payable_amount_cent = max(0, list_amount_cent - first_order_discount_cent - normalized_coupon_discount_cent)
        return MembershipOrderPreview(
            user_id=str(user_id),
            plan_id=normalized_plan_id,
            plan_name=_membership_plan_name(normalized_plan_id),
            order_type="first_purchase" if is_first else "renewal",
            period_days=period_days,
            list_amount_cent=list_amount_cent,
            first_order_discount_cent=first_order_discount_cent,
            coupon_discount_cent=normalized_coupon_discount_cent,
            payable_amount_cent=payable_amount_cent,
            coupon_id=None if not coupon_id else str(coupon_id),
        )

    def _row_to_order(self, row: sqlite3.Row) -> MembershipOrder:
        return MembershipOrder(
            order_id=str(row["order_id"]),
            user_id=str(row["user_id"]),
            plan_id=_normalize_membership_plan_id(row["plan_id"] if "plan_id" in row.keys() else MEMBERSHIP_PLAN_MONTHLY),
            plan_name=_membership_plan_name(row["plan_id"] if "plan_id" in row.keys() else MEMBERSHIP_PLAN_MONTHLY),
            order_type=str(row["order_type"]),
            pricing_version=str(row["pricing_version"]),
            period_days=int(row["period_days"]),
            list_amount_cent=int(row["list_amount_cent"]),
            first_order_discount_cent=int(row["first_order_discount_cent"]),
            coupon_discount_cent=int(row["coupon_discount_cent"] or 0),
            payable_amount_cent=int(row["payable_amount_cent"]),
            coupon_id=None if row["coupon_id"] is None else str(row["coupon_id"]),
            provider=str(row["provider"]),
            provider_trade_no=None if row["provider_trade_no"] is None else str(row["provider_trade_no"]),
            status=str(row["status"]),
            client_ip=str(row["client_ip"] or ""),
            client_version=str(row["client_version"] or ""),
            created_at=str(row["created_at"]),
            paid_at=None if row["paid_at"] is None else str(row["paid_at"]),
            closed_at=None if row["closed_at"] is None else str(row["closed_at"]),
            refunded_at=None if row["refunded_at"] is None else str(row["refunded_at"]),
            expired_at=None if row["expired_at"] is None else str(row["expired_at"]),
            entitlement_id=None if row["entitlement_id"] is None else str(row["entitlement_id"]),
            remark=str(row["remark"] or ""),
        )

    def _row_to_payment(self, row: sqlite3.Row) -> MembershipPaymentRecord:
        return MembershipPaymentRecord(
            payment_id=str(row["payment_id"]),
            order_id=str(row["order_id"]),
            provider=str(row["provider"]),
            provider_trade_no=str(row["provider_trade_no"]),
            provider_buyer_id=str(row["provider_buyer_id"] or ""),
            amount_cent=int(row["amount_cent"]),
            status=str(row["status"]),
            callback_payload_json=str(row["callback_payload_json"] or ""),
            created_at=str(row["created_at"]),
            confirmed_at=None if row["confirmed_at"] is None else str(row["confirmed_at"]),
            refund_out_refund_no=None if row["refund_out_refund_no"] is None else str(row["refund_out_refund_no"]),
            refund_callback_payload_json=str(row["refund_callback_payload_json"] or ""),
            refund_requested_at=None if row["refund_requested_at"] is None else str(row["refund_requested_at"]),
            refunded_at=None if row["refunded_at"] is None else str(row["refunded_at"]),
        )

    def _summary_from_conn(self, conn: sqlite3.Connection, user_id: str) -> MembershipSummary:
        now = _utc_now()
        self._sync_expired_rows(conn, user_id=user_id, now=now)
        latest_entitlement = conn.execute(
            """
            SELECT entitlement_id, start_at, end_at, status
            FROM membership_entitlements
            WHERE user_id = ?
              AND status IN ('active', 'expired')
            ORDER BY end_at DESC, granted_at DESC
            LIMIT 1
            """,
            (str(user_id),),
        ).fetchone()
        if latest_entitlement is None:
            row = conn.execute(
                "SELECT 1 FROM membership_orders WHERE user_id = ? AND status = 'paid' LIMIT 1",
                (str(user_id),),
            ).fetchone()
            current_status = "expired" if row is not None else "never_purchased"
            current_starts_at = None
            current_ends_at = None
            is_active = False
        else:
            current_starts_at = str(latest_entitlement["start_at"])
            current_ends_at = str(latest_entitlement["end_at"])
            current_status = "active" if str(latest_entitlement["status"]) == "active" else "expired"
            is_active = current_status == "active"
        is_first_order_eligible = self._is_first_order_eligible(conn, user_id)
        return MembershipSummary(
            user_id=str(user_id),
            current_status=current_status,
            current_starts_at=current_starts_at,
            current_ends_at=current_ends_at,
            is_active=is_active,
            is_first_order_eligible=is_first_order_eligible,
            base_monthly_price_cent=BASE_MONTHLY_PRICE_CENT,
            first_order_price_cent=FIRST_ORDER_PRICE_CENT,
            renewal_price_cent=RENEWAL_PRICE_CENT,
            current_price_cent=FIRST_ORDER_PRICE_CENT if is_first_order_eligible else RENEWAL_PRICE_CENT,
            supported_payment_providers=list_supported_membership_payment_providers(),
        )

    def get_membership_summary(self, user_id: str) -> MembershipSummary:
        conn = self._connect()
        try:
            return self._summary_from_conn(conn, str(user_id))
        finally:
            conn.close()

    def preview_order(
        self,
        user_id: str,
        *,
        plan_id: str | None = None,
        coupon_discount_cent: int = 0,
        coupon_id: str | None = None,
    ) -> MembershipOrderPreview:
        conn = self._connect()
        try:
            self._sync_expired_rows(conn, user_id=str(user_id))
            return self._preview_for_user(
                conn,
                str(user_id),
                plan_id=plan_id,
                coupon_discount_cent=coupon_discount_cent,
                coupon_id=coupon_id,
            )
        finally:
            conn.close()

    def list_orders(self, user_id: str, *, limit: int = 20) -> tuple[MembershipOrder, ...]:
        normalized_limit = _normalize_limit(limit)
        conn = self._connect()
        try:
            self._sync_expired_rows(conn, user_id=str(user_id))
            rows = conn.execute(
                """
                SELECT *
                FROM membership_orders
                WHERE user_id = ?
                ORDER BY created_at DESC, order_id DESC
                LIMIT ?
                """,
                (str(user_id), normalized_limit),
            ).fetchall()
            return tuple(self._row_to_order(row) for row in rows)
        finally:
            conn.close()

    def get_order(self, order_id: str) -> MembershipOrder:
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        conn = self._connect()
        try:
            self._sync_expired_rows(conn)
            row = conn.execute(
                "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                (normalized_order_id,),
            ).fetchone()
            if row is None:
                raise NotFound("membership order")
            return self._row_to_order(row)
        finally:
            conn.close()

    def get_order_for_user(self, user_id: str, order_id: str) -> MembershipOrder:
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        conn = self._connect()
        try:
            self._sync_expired_rows(conn, user_id=str(user_id))
            row = conn.execute(
                "SELECT * FROM membership_orders WHERE order_id = ? AND user_id = ? LIMIT 1",
                (normalized_order_id, str(user_id)),
            ).fetchone()
            if row is None:
                raise NotFound("membership order")
            return self._row_to_order(row)
        finally:
            conn.close()

    @staticmethod
    def _latest_payment_row_for_order(conn: sqlite3.Connection, order_id: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT *
            FROM membership_payments
            WHERE order_id = ?
            ORDER BY COALESCE(confirmed_at, created_at) DESC, created_at DESC, payment_id DESC
            LIMIT 1
            """,
            (str(order_id),),
        ).fetchone()

    def get_payment_for_order(self, order_id: str) -> MembershipPaymentRecord:
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        conn = self._connect()
        try:
            row = self._latest_payment_row_for_order(conn, normalized_order_id)
            if row is None:
                raise NotFound("membership payment")
            return self._row_to_payment(row)
        finally:
            conn.close()

    def find_payment_for_order(self, order_id: str) -> MembershipPaymentRecord | None:
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        conn = self._connect()
        try:
            row = self._latest_payment_row_for_order(conn, normalized_order_id)
            return None if row is None else self._row_to_payment(row)
        finally:
            conn.close()

    def get_admin_overview(self) -> MembershipAdminOverview:
        conn = self._connect()
        try:
            self._sync_expired_rows(conn)
            row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM membership_orders WHERE status = 'paid') AS paid_order_count,
                    (SELECT COUNT(*) FROM membership_orders WHERE status = 'pending') AS pending_order_count,
                    (SELECT COUNT(*) FROM membership_orders WHERE status = 'paid' AND order_type = 'first_purchase') AS first_purchase_paid_count,
                    (SELECT COUNT(*) FROM membership_orders WHERE status = 'paid' AND order_type = 'renewal') AS renewal_paid_count,
                    (SELECT COUNT(DISTINCT user_id) FROM membership_entitlements WHERE status = 'active') AS active_membership_count,
                    (SELECT COALESCE(SUM(payable_amount_cent), 0) FROM membership_orders WHERE status = 'paid') AS total_paid_amount_cent
                """
            ).fetchone()
            return MembershipAdminOverview(
                paid_order_count=0 if row is None else int(row["paid_order_count"] or 0),
                active_membership_count=0 if row is None else int(row["active_membership_count"] or 0),
                total_paid_amount_cent=0 if row is None else int(row["total_paid_amount_cent"] or 0),
                first_purchase_paid_count=0 if row is None else int(row["first_purchase_paid_count"] or 0),
                renewal_paid_count=0 if row is None else int(row["renewal_paid_count"] or 0),
                pending_order_count=0 if row is None else int(row["pending_order_count"] or 0),
            )
        finally:
            conn.close()

    def _rebuild_user_entitlements(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        *,
        now: datetime | None = None,
        revoked_reason: str = "",
    ) -> None:
        resolved_now = now or _utc_now()
        resolved_now_text = resolved_now.isoformat()
        normalized_reason = str(revoked_reason or "").strip() or "membership order refunded"
        paid_rows = conn.execute(
            """
            SELECT *
            FROM membership_orders
            WHERE user_id = ?
              AND status = 'paid'
            ORDER BY COALESCE(paid_at, created_at) ASC, created_at ASC, order_id ASC
            """,
            (str(user_id),),
        ).fetchall()

        retained_order_ids: set[str] = set()
        current_chain_end_at: datetime | None = None
        for row in paid_rows:
            order = self._row_to_order(row)
            retained_order_ids.add(order.order_id)
            anchor_at = _parse_dt(order.paid_at or order.created_at)
            start_at = anchor_at if current_chain_end_at is None or current_chain_end_at <= anchor_at else current_chain_end_at
            end_at = start_at + timedelta(days=order.period_days)
            current_chain_end_at = end_at
            entitlement_status = "expired" if end_at <= resolved_now else "active"
            entitlement_row = conn.execute(
                """
                SELECT entitlement_id, granted_at
                FROM membership_entitlements
                WHERE source_order_id = ?
                LIMIT 1
                """,
                (order.order_id,),
            ).fetchone()
            if entitlement_row is None:
                entitlement_id = order.entitlement_id or f"ment_{uuid.uuid4().hex}"
                granted_at = order.paid_at or order.created_at
                conn.execute(
                    """
                    INSERT INTO membership_entitlements (
                        entitlement_id,
                        user_id,
                        source_order_id,
                        start_at,
                        end_at,
                        granted_days,
                        status,
                        granted_at,
                        revoked_at,
                        revoke_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, '')
                    """,
                    (
                        entitlement_id,
                        str(user_id),
                        order.order_id,
                        start_at.isoformat(),
                        end_at.isoformat(),
                        order.period_days,
                        entitlement_status,
                        granted_at,
                    ),
                )
            else:
                entitlement_id = str(entitlement_row["entitlement_id"])
                granted_at = str(entitlement_row["granted_at"] or order.paid_at or order.created_at)
                conn.execute(
                    """
                    UPDATE membership_entitlements
                    SET user_id = ?,
                        start_at = ?,
                        end_at = ?,
                        granted_days = ?,
                        status = ?,
                        granted_at = ?,
                        revoked_at = NULL,
                        revoke_reason = ''
                    WHERE entitlement_id = ?
                    """,
                    (
                        str(user_id),
                        start_at.isoformat(),
                        end_at.isoformat(),
                        order.period_days,
                        entitlement_status,
                        granted_at,
                        entitlement_id,
                    ),
                )
            if order.entitlement_id != entitlement_id:
                conn.execute(
                    "UPDATE membership_orders SET entitlement_id = ? WHERE order_id = ?",
                    (entitlement_id, order.order_id),
                )

        entitlement_rows = conn.execute(
            """
            SELECT e.entitlement_id, e.source_order_id, e.source_kind, COALESCE(o.status, '') AS order_status
            FROM membership_entitlements e
            LEFT JOIN membership_orders o ON o.order_id = e.source_order_id
            WHERE e.user_id = ?
            """,
            (str(user_id),),
        ).fetchall()
        for entitlement_row in entitlement_rows:
            if str(entitlement_row["source_kind"] or "order") != "order":
                continue
            source_order_id = str(entitlement_row["source_order_id"])
            if source_order_id in retained_order_ids:
                continue
            order_status = str(entitlement_row["order_status"] or "")
            effective_reason = normalized_reason if order_status == "refunded" else "membership order is no longer active"
            conn.execute(
                """
                UPDATE membership_entitlements
                SET status = 'revoked',
                    revoked_at = COALESCE(revoked_at, ?),
                    revoke_reason = CASE WHEN revoke_reason = '' THEN ? ELSE revoke_reason END
                WHERE entitlement_id = ?
                """,
                (
                    resolved_now_text,
                    effective_reason,
                    str(entitlement_row["entitlement_id"]),
                ),
            )

    def _restore_coupon_after_refund(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        now: datetime,
    ) -> tuple[str | None, str | None]:
        if not order.coupon_id or not self._table_exists(conn, "coupons"):
            return None, None
        coupon_row = conn.execute(
            """
            SELECT coupon_id, status, expires_at, used_order_id
            FROM coupons
            WHERE coupon_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (order.coupon_id, order.user_id),
        ).fetchone()
        if coupon_row is None:
            return None, None
        coupon_status = str(coupon_row["status"])
        if coupon_status == COUPON_STATUS_USED and str(coupon_row["used_order_id"] or "") == order.order_id:
            expires_at = None if coupon_row["expires_at"] is None else _parse_dt(str(coupon_row["expires_at"]))
            restored_status = COUPON_STATUS_EXPIRED if expires_at is not None and expires_at <= now else COUPON_STATUS_AVAILABLE
            conn.execute(
                """
                UPDATE coupons
                SET status = ?,
                    used_order_id = NULL,
                    used_at = NULL
                WHERE coupon_id = ?
                """,
                (
                    restored_status,
                    order.coupon_id,
                ),
            )
            return order.coupon_id, restored_status
        if coupon_status in {COUPON_STATUS_AVAILABLE, COUPON_STATUS_EXPIRED}:
            return order.coupon_id, coupon_status
        return order.coupon_id, coupon_status

    def _rollback_invite_reward_for_refund(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        now: datetime,
        reason: str,
    ) -> str | None:
        if order.order_type != "first_purchase":
            return None
        if not self._table_exists(conn, "invite_bindings") or not self._table_exists(conn, "invite_reward_records"):
            return None
        reward_row = conn.execute(
            """
            SELECT reward_id, coupon_id
            FROM invite_reward_records
            WHERE trigger_order_id = ?
            LIMIT 1
            """,
            (order.order_id,),
        ).fetchone()
        if reward_row is None:
            return None
        reward_coupon_id = str(reward_row["coupon_id"])
        if self._table_exists(conn, "coupons"):
            coupon_row = conn.execute(
                """
                SELECT status
                FROM coupons
                WHERE coupon_id = ?
                LIMIT 1
                """,
                (reward_coupon_id,),
            ).fetchone()
            if coupon_row is not None:
                reward_coupon_status = str(coupon_row["status"] or "")
                if reward_coupon_status == COUPON_STATUS_USED:
                    raise PreconditionFailure("invite reward coupon has already been used and must be handled before refunding this order")
                if reward_coupon_status == COUPON_STATUS_AVAILABLE:
                    conn.execute(
                        """
                        UPDATE coupons
                        SET status = ?,
                            revoked_at = ?,
                            revoke_reason = ?
                        WHERE coupon_id = ?
                        """,
                        (
                            COUPON_STATUS_REVOKED,
                            now.isoformat(),
                            reason,
                            reward_coupon_id,
                        ),
                    )
        conn.execute(
            """
            UPDATE invite_reward_records
            SET status = ?,
                revoked_at = ?
            WHERE reward_id = ?
            """,
            (
                REWARD_STATUS_REVOKED,
                now.isoformat(),
                str(reward_row["reward_id"]),
            ),
        )
        conn.execute(
            """
            UPDATE invite_bindings
            SET status = ?,
                rewarded_at = NULL,
                reward_trigger_order_id = NULL,
                reward_coupon_id = NULL
            WHERE invitee_user_id = ?
              AND reward_trigger_order_id = ?
            """,
            (
                INVITE_BINDING_STATUS_BOUND,
                order.user_id,
                order.order_id,
            ),
        )
        return reward_coupon_id

    def list_admin_orders(
        self,
        *,
        status: str | None = None,
        order_type: str | None = None,
        provider: str | None = None,
        limit: int = 100,
    ) -> tuple[MembershipOrder, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        clauses: list[str] = []
        params: list[object] = []
        normalized_status = str(status or "").strip().lower()
        if normalized_status and normalized_status != "all":
            clauses.append("status = ?")
            params.append(normalized_status)
        normalized_order_type = str(order_type or "").strip().lower()
        if normalized_order_type and normalized_order_type != "all":
            clauses.append("order_type = ?")
            params.append(normalized_order_type)
        normalized_provider = str(provider or "").strip().lower()
        if normalized_provider and normalized_provider != "all":
            clauses.append("provider = ?")
            params.append(normalized_provider)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(normalized_limit)
        conn = self._connect()
        try:
            self._sync_expired_rows(conn)
            rows = conn.execute(
                f"""
                SELECT *
                FROM membership_orders
                {where}
                ORDER BY created_at DESC, order_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_order(row) for row in rows)
        finally:
            conn.close()

    def grant_membership_months(self, user_id: str, *, months: int) -> MembershipGrantResult:
        normalized_months = int(months)
        if normalized_months < 1 or normalized_months > 24:
            raise PreconditionFailure("membership grant months must be between 1 and 24")
        granted_days = MEMBERSHIP_PERIOD_DAYS * normalized_months
        now = _utc_now()
        source_ref_id = f"admin_grant_{uuid.uuid4().hex}"
        entitlement_id = f"ment_{uuid.uuid4().hex}"
        conn = self._connect()
        try:
            with self._lock:
                self._sync_expired_rows(conn, user_id=str(user_id), now=now)
                summary_before = self._summary_from_conn(conn, str(user_id))
                start_at_dt = now if not summary_before.is_active or not summary_before.current_ends_at else _parse_dt(summary_before.current_ends_at)
                end_at_dt = start_at_dt + timedelta(days=granted_days)
                status = "expired" if end_at_dt <= now else "active"
                conn.execute(
                    """
                    INSERT INTO membership_entitlements (
                        entitlement_id,
                        user_id,
                        source_order_id,
                        source_kind,
                        start_at,
                        end_at,
                        granted_days,
                        status,
                        granted_at,
                        revoked_at,
                        revoke_reason
                    )
                    VALUES (?, ?, ?, 'admin_grant', ?, ?, ?, ?, ?, NULL, '')
                    """,
                    (
                        entitlement_id,
                        str(user_id),
                        source_ref_id,
                        start_at_dt.isoformat(),
                        end_at_dt.isoformat(),
                        granted_days,
                        status,
                        now.isoformat(),
                    ),
                )
                conn.commit()
                membership = self._summary_from_conn(conn, str(user_id))
                return MembershipGrantResult(
                    user_id=str(user_id),
                    entitlement_id=entitlement_id,
                    source_ref_id=source_ref_id,
                    months=normalized_months,
                    granted_days=granted_days,
                    start_at=start_at_dt.isoformat(),
                    end_at=end_at_dt.isoformat(),
                    membership=membership,
                )
        finally:
            conn.close()

    def list_pending_payment_sync_candidates(
        self,
        *,
        provider: str,
        older_than_minutes: int = 5,
        limit: int = 100,
        now: datetime | None = None,
    ) -> tuple[MembershipOrder, ...]:
        normalized_provider = _normalize_provider(provider)
        normalized_limit = _normalize_limit(limit, default=100, maximum=500)
        normalized_age_minutes = max(0, int(older_than_minutes))
        resolved_now = now or _utc_now()
        cutoff = resolved_now - timedelta(minutes=normalized_age_minutes)
        conn = self._connect()
        try:
            self._sync_expired_rows(conn, now=resolved_now)
            rows = conn.execute(
                """
                SELECT *
                FROM membership_orders
                WHERE provider = ?
                  AND status = 'pending'
                  AND created_at <= ?
                ORDER BY created_at ASC, order_id ASC
                LIMIT ?
                """,
                (
                    normalized_provider,
                    cutoff.isoformat(),
                    normalized_limit,
                ),
            ).fetchall()
            return tuple(self._row_to_order(row) for row in rows)
        finally:
            conn.close()

    def create_order(
        self,
        user_id: str,
        *,
        provider: str,
        client_ip: str = "",
        client_version: str = "",
        plan_id: str | None = None,
        coupon_id: str | None = None,
        coupon_discount_cent: int = 0,
    ) -> MembershipCreateOrderResult:
        normalized_provider = _normalize_provider(provider)
        normalized_plan_id = _normalize_membership_plan_id(plan_id)
        normalized_coupon_discount_cent = max(0, int(coupon_discount_cent))
        normalized_coupon_id = str(coupon_id or "").strip() or None
        now = _utc_now()
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, user_id=str(user_id), now=now)
                preview = self._preview_for_user(
                    conn,
                    str(user_id),
                    plan_id=normalized_plan_id,
                    coupon_discount_cent=normalized_coupon_discount_cent,
                    coupon_id=normalized_coupon_id,
                    now=now,
                )
                existing = conn.execute(
                    """
                    SELECT *
                    FROM membership_orders
                    WHERE user_id = ?
                      AND provider = ?
                      AND status = 'pending'
                    ORDER BY created_at DESC, order_id DESC
                    LIMIT 1
                    """,
                    (str(user_id), normalized_provider),
                ).fetchone()
                if existing is not None:
                    expired_at = (now + timedelta(minutes=ORDER_TTL_MINUTES)).isoformat()
                    conn.execute(
                        """
                        UPDATE membership_orders
                        SET plan_id = ?,
                            order_type = ?,
                            pricing_version = ?,
                            period_days = ?,
                            list_amount_cent = ?,
                            first_order_discount_cent = ?,
                            coupon_discount_cent = ?,
                            payable_amount_cent = ?,
                            coupon_id = ?,
                            client_ip = ?,
                            client_version = ?,
                            expired_at = ?
                        WHERE order_id = ?
                        """,
                        (
                            preview.plan_id,
                            preview.order_type,
                            MEMBERSHIP_PRICING_VERSION,
                            preview.period_days,
                            preview.list_amount_cent,
                            preview.first_order_discount_cent,
                            preview.coupon_discount_cent,
                            preview.payable_amount_cent,
                            preview.coupon_id,
                            str(client_ip or ""),
                            str(client_version or ""),
                            expired_at,
                            str(existing["order_id"]),
                        ),
                    )
                    row = conn.execute(
                        "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                        (str(existing["order_id"]),),
                    ).fetchone()
                    if row is None:
                        raise NotFound("membership order")
                    conn.commit()
                    order = self._row_to_order(row)
                    return MembershipCreateOrderResult(
                        order=order,
                        reused_existing_order=True,
                    )

                order_id = f"mord_{uuid.uuid4().hex}"
                created_at = now.isoformat()
                expired_at = (now + timedelta(minutes=ORDER_TTL_MINUTES)).isoformat()
                conn.execute(
                    """
                    INSERT INTO membership_orders (
                        order_id,
                        user_id,
                        plan_id,
                        order_type,
                        pricing_version,
                        period_days,
                        list_amount_cent,
                        first_order_discount_cent,
                        coupon_discount_cent,
                        payable_amount_cent,
                        coupon_id,
                        provider,
                        status,
                        client_ip,
                        client_version,
                        created_at,
                        expired_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        str(user_id),
                        preview.plan_id,
                        preview.order_type,
                        MEMBERSHIP_PRICING_VERSION,
                        preview.period_days,
                        preview.list_amount_cent,
                        preview.first_order_discount_cent,
                        preview.coupon_discount_cent,
                        preview.payable_amount_cent,
                        preview.coupon_id,
                        normalized_provider,
                        str(client_ip or ""),
                        str(client_version or ""),
                        created_at,
                        expired_at,
                    ),
                )
                row = conn.execute("SELECT * FROM membership_orders WHERE order_id = ?", (order_id,)).fetchone()
                if row is None:
                    raise NotFound("membership order")
                conn.commit()
                order = self._row_to_order(row)
                return MembershipCreateOrderResult(
                    order=order,
                    reused_existing_order=False,
                )
            finally:
                conn.close()

    @staticmethod
    def _latest_payment_row_for_provider_trade_no(
        conn: sqlite3.Connection,
        *,
        provider: str,
        provider_trade_no: str,
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT *
            FROM membership_payments
            WHERE provider = ? AND provider_trade_no = ?
            LIMIT 1
            """,
            (str(provider), str(provider_trade_no)),
        ).fetchone()

    def _upsert_terminal_payment_locked(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        provider_trade_no: str,
        payment_status: str,
        callback_payload_json: str,
        provider_buyer_id: str | None = None,
        amount_cent: int | None = None,
        synced_at: str | None = None,
    ) -> str:
        resolved_provider_trade_no = str(provider_trade_no or "").strip()
        if not resolved_provider_trade_no:
            raise PreconditionFailure("membership providerTradeNo must be non-empty")
        resolved_status = str(payment_status or "").strip() or "failed"
        if resolved_status not in {"failed", "refund_pending", "refunded", "succeeded"}:
            raise PreconditionFailure("membership payment status is unsupported")
        resolved_synced_at = str(synced_at or _utc_now().isoformat()).strip()
        resolved_payload = str(callback_payload_json or "").strip()
        if not resolved_payload:
            resolved_payload = json.dumps(
                {
                    "orderId": order.order_id,
                    "provider": order.provider,
                    "providerTradeNo": resolved_provider_trade_no,
                    "status": resolved_status,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        resolved_amount_cent = order.payable_amount_cent
        if amount_cent is not None and int(amount_cent) > 0:
            resolved_amount_cent = int(amount_cent)
        existing = self._latest_payment_row_for_provider_trade_no(
            conn,
            provider=order.provider,
            provider_trade_no=resolved_provider_trade_no,
        )
        if existing is not None:
            if str(existing["order_id"]) != order.order_id:
                raise PreconditionFailure("membership payment trade number is already bound to another order")
            conn.execute(
                """
                UPDATE membership_payments
                SET provider_buyer_id = ?,
                    amount_cent = ?,
                    status = ?,
                    callback_payload_json = ?,
                    confirmed_at = ?
                WHERE payment_id = ?
                """,
                (
                    str(provider_buyer_id or ""),
                    resolved_amount_cent,
                    resolved_status,
                    resolved_payload,
                    resolved_synced_at,
                    str(existing["payment_id"]),
                ),
            )
            return str(existing["payment_id"])
        payment_id = f"mpay_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO membership_payments (
                payment_id,
                order_id,
                provider,
                provider_trade_no,
                provider_buyer_id,
                amount_cent,
                status,
                callback_payload_json,
                created_at,
                confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                order.order_id,
                order.provider,
                resolved_provider_trade_no,
                str(provider_buyer_id or ""),
                resolved_amount_cent,
                resolved_status,
                resolved_payload,
                resolved_synced_at,
                resolved_synced_at,
            ),
        )
        return payment_id

    def _close_order_locked(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        closed_at: str | None = None,
        reason: str = "",
    ) -> MembershipOrderCloseResult:
        resolved_reason = str(reason or "").strip()
        if order.status == "closed":
            conn.commit()
            membership = self._summary_from_conn(conn, str(order.user_id))
            refreshed_order_row = conn.execute(
                "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                (order.order_id,),
            ).fetchone()
            if refreshed_order_row is None:
                raise NotFound("membership order")
            return MembershipOrderCloseResult(
                order=self._row_to_order(refreshed_order_row),
                membership=membership,
                idempotent=True,
            )
        if order.status != "pending":
            raise PreconditionFailure("only pending membership orders can be closed")
        resolved_closed_at = str(closed_at or _utc_now().isoformat()).strip()
        conn.execute(
            """
            UPDATE membership_orders
            SET status = 'closed',
                closed_at = ?,
                remark = ?
            WHERE order_id = ?
            """,
            (
                resolved_closed_at,
                resolved_reason,
                order.order_id,
            ),
        )
        refreshed_order_row = conn.execute(
            "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
            (order.order_id,),
        ).fetchone()
        if refreshed_order_row is None:
            raise NotFound("membership order")
        conn.commit()
        membership = self._summary_from_conn(conn, str(order.user_id))
        return MembershipOrderCloseResult(
            order=self._row_to_order(refreshed_order_row),
            membership=membership,
            idempotent=False,
        )

    def close_order_for_user(
        self,
        user_id: str,
        order_id: str,
        *,
        reason: str = "",
    ) -> MembershipOrderCloseResult:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, user_id=str(user_id))
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? AND user_id = ? LIMIT 1",
                    (normalized_order_id, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                return self._close_order_locked(conn, self._row_to_order(row), reason=reason)
            finally:
                conn.close()

    def close_order(
        self,
        order_id: str,
        *,
        reason: str = "",
    ) -> MembershipOrderCloseResult:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn)
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                return self._close_order_locked(conn, self._row_to_order(row), reason=reason)
            finally:
                conn.close()

    def sync_provider_payment_status(
        self,
        *,
        order_id: str,
        remote_status: MembershipRemotePaymentStatus,
    ) -> MembershipPaymentSyncResult:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        if str(remote_status.order_id or "").strip() != normalized_order_id:
            raise PreconditionFailure("membership payment sync orderId does not match the remote payload")
        if remote_status.remote_status == "paid":
            confirmed = self.confirm_provider_payment(
                order_id=remote_status.order_id,
                provider=remote_status.provider,
                provider_trade_no=remote_status.provider_trade_no,
                amount_cent=remote_status.amount_cent,
                paid_at=remote_status.paid_at,
                payer_id=remote_status.payer_id,
                callback_payload_json=remote_status.raw_payload_json,
            )
            return MembershipPaymentSyncResult(
                order=confirmed.order,
                membership=confirmed.membership,
                payment_id=confirmed.payment_id,
                confirmed=True,
                idempotent=confirmed.idempotent,
            )

        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn)
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(row)
                payment_id: str | None = None
                idempotent = False
                if remote_status.remote_status in {"closed", "failed", "refunded"}:
                    if order.status not in {"pending", "closed"}:
                        membership = self._summary_from_conn(conn, str(order.user_id))
                        payment = self._latest_payment_row_for_order(conn, normalized_order_id)
                        if payment is not None:
                            payment_id = str(payment["payment_id"])
                        return MembershipPaymentSyncResult(
                            order=order,
                            membership=membership,
                            payment_id=payment_id,
                            confirmed=False,
                            idempotent=True,
                        )
                    payment_id = self._upsert_terminal_payment_locked(
                        conn,
                        order,
                        provider_trade_no=remote_status.provider_trade_no,
                        payment_status="failed",
                        callback_payload_json=remote_status.raw_payload_json,
                        provider_buyer_id=remote_status.payer_id,
                        amount_cent=remote_status.amount_cent,
                        synced_at=remote_status.paid_at or _utc_now().isoformat(),
                    )
                    close_reason = f"remote payment state: {remote_status.remote_status}"
                    closed = self._close_order_locked(conn, order, reason=close_reason)
                    return MembershipPaymentSyncResult(
                        order=closed.order,
                        membership=closed.membership,
                        payment_id=payment_id,
                        confirmed=False,
                        idempotent=closed.idempotent,
                    )
                refreshed_order_row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if refreshed_order_row is None:
                    raise NotFound("membership order")
                membership = self._summary_from_conn(conn, str(order.user_id))
                payment = self._latest_payment_row_for_order(conn, normalized_order_id)
                if payment is not None:
                    payment_id = str(payment["payment_id"])
                if order.status != "pending":
                    idempotent = True
                return MembershipPaymentSyncResult(
                    order=self._row_to_order(refreshed_order_row),
                    membership=membership,
                    payment_id=payment_id,
                    confirmed=False,
                    idempotent=idempotent,
                )
            finally:
                conn.close()

    def _grant_invite_reward_locked(
        self,
        conn: sqlite3.Connection,
        *,
        order: MembershipOrder,
        confirmed_at: str,
        confirmed_at_dt: datetime,
    ) -> None:
        if order.order_type != "first_purchase":
            return
        if not self._table_exists(conn, "invite_bindings"):
            return
        invite_binding_row = conn.execute(
            """
            SELECT inviter_user_id
            FROM invite_bindings
            WHERE invitee_user_id = ?
            LIMIT 1
            """,
            (str(order.user_id),),
        ).fetchone()
        if invite_binding_row is None:
            return
        self._ensure_commission_tables(conn)
        commission_row = conn.execute(
            """
            SELECT commission_id
            FROM commission_records
            WHERE source_order_id = ?
            LIMIT 1
            """,
            (order.order_id,),
        ).fetchone()
        if commission_row is not None:
            return
        if order.payable_amount_cent < 1500:
            return
        commission_id = f"mcom_{uuid.uuid4().hex}"
        refund_window_ends_at = (confirmed_at_dt + timedelta(minutes=commission_refund_window_minutes())).isoformat()
        inviter_user_id = str(invite_binding_row["inviter_user_id"])
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
            VALUES (?, ?, ?, ?, ?, 1500, 500, ?, 'pending', ?)
            """,
            (
                commission_id,
                inviter_user_id,
                str(order.user_id),
                order.order_id,
                order.payable_amount_cent,
                refund_window_ends_at,
                confirmed_at,
            ),
        )
        conn.execute(
            """
            UPDATE invite_bindings
            SET status = ?,
                reward_trigger_order_id = ?
            WHERE invitee_user_id = ?
            """,
            (
                INVITE_BINDING_STATUS_COMMISSION_PENDING,
                order.order_id,
                str(order.user_id),
            ),
        )

    def _confirm_payment_locked(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        provider_trade_no: str,
        confirmed_at: str | None = None,
        callback_payload_json: str = "",
        provider_buyer_id: str | None = None,
    ) -> MembershipPaymentConfirmation:
        resolved_provider_trade_no = str(provider_trade_no or "").strip()
        if not resolved_provider_trade_no:
            raise PreconditionFailure("membership providerTradeNo must be non-empty")
        confirmed_at_dt = _utc_now() if not confirmed_at else _parse_dt(confirmed_at)
        confirmed_at_text = confirmed_at_dt.isoformat()
        self._sync_expired_rows(conn, user_id=str(order.user_id), now=confirmed_at_dt)

        payment_row = conn.execute(
            """
            SELECT payment_id, order_id
            FROM membership_payments
            WHERE provider = ? AND provider_trade_no = ?
            LIMIT 1
            """,
            (order.provider, resolved_provider_trade_no),
        ).fetchone()
        if payment_row is not None:
            if str(payment_row["order_id"]) != order.order_id:
                raise PreconditionFailure("membership payment trade number is already bound to another order")
            refreshed_order_row = conn.execute(
                "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                (order.order_id,),
            ).fetchone()
            if refreshed_order_row is None:
                raise NotFound("membership order")
            membership = self._summary_from_conn(conn, str(order.user_id))
            return MembershipPaymentConfirmation(
                order=self._row_to_order(refreshed_order_row),
                membership=membership,
                payment_id=str(payment_row["payment_id"]),
                idempotent=True,
            )

        if order.status == "paid":
            raise PreconditionFailure("membership order has already been paid")
        if order.status != "pending":
            raise PreconditionFailure("membership order is not awaiting payment")
        if order.expired_at and _parse_dt(order.expired_at) <= confirmed_at_dt:
            conn.execute(
                "UPDATE membership_orders SET status = 'expired' WHERE order_id = ?",
                (order.order_id,),
            )
            conn.commit()
            raise PreconditionFailure("membership order has expired")
        if order.coupon_id:
            if not self._table_exists(conn, "coupons"):
                raise PreconditionFailure("membership coupon storage is unavailable")
            coupon_row = conn.execute(
                """
                SELECT coupon_id, status, min_spend_cent
                FROM coupons
                WHERE coupon_id = ? AND user_id = ?
                LIMIT 1
                """,
                (order.coupon_id, str(order.user_id)),
            ).fetchone()
            if coupon_row is None or str(coupon_row["status"]) != COUPON_STATUS_AVAILABLE:
                raise PreconditionFailure("membership order coupon is unavailable")
            pre_coupon_amount_cent = order.payable_amount_cent + order.coupon_discount_cent
            if int(coupon_row["min_spend_cent"] or 0) > pre_coupon_amount_cent:
                raise PreconditionFailure("membership order coupon no longer meets the minimum spend")

        latest_active_entitlement = conn.execute(
            """
            SELECT end_at
            FROM membership_entitlements
            WHERE user_id = ? AND status = 'active'
            ORDER BY end_at DESC, granted_at DESC
            LIMIT 1
            """,
            (str(order.user_id),),
        ).fetchone()
        start_at_dt = confirmed_at_dt
        if latest_active_entitlement is not None:
            previous_end_at = _parse_dt(str(latest_active_entitlement["end_at"]))
            if previous_end_at > start_at_dt:
                start_at_dt = previous_end_at
        end_at_dt = start_at_dt + timedelta(days=order.period_days)

        payment_id = f"mpay_{uuid.uuid4().hex}"
        entitlement_id = f"ment_{uuid.uuid4().hex}"
        resolved_payload = str(callback_payload_json or "").strip()
        if not resolved_payload:
            resolved_payload = json.dumps(
                {
                    "orderId": order.order_id,
                    "provider": order.provider,
                    "providerTradeNo": resolved_provider_trade_no,
                    "userId": str(order.user_id),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        conn.execute(
            """
            INSERT INTO membership_payments (
                payment_id,
                order_id,
                provider,
                provider_trade_no,
                provider_buyer_id,
                amount_cent,
                status,
                callback_payload_json,
                created_at,
                confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'succeeded', ?, ?, ?)
            """,
            (
                payment_id,
                order.order_id,
                order.provider,
                resolved_provider_trade_no,
                str(provider_buyer_id or ""),
                order.payable_amount_cent,
                resolved_payload,
                confirmed_at_text,
                confirmed_at_text,
            ),
        )
        conn.execute(
            """
            INSERT INTO membership_entitlements (
                entitlement_id,
                user_id,
                source_order_id,
                start_at,
                end_at,
                granted_days,
                status,
                granted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                entitlement_id,
                str(order.user_id),
                order.order_id,
                start_at_dt.isoformat(),
                end_at_dt.isoformat(),
                order.period_days,
                confirmed_at_text,
            ),
        )
        conn.execute(
            """
            UPDATE membership_orders
            SET status = 'paid',
                provider_trade_no = ?,
                paid_at = ?,
                entitlement_id = ?
            WHERE order_id = ?
            """,
            (
                resolved_provider_trade_no,
                confirmed_at_text,
                entitlement_id,
                order.order_id,
            ),
        )
        if order.coupon_id:
            coupon_update = conn.execute(
                """
                UPDATE coupons
                SET status = 'used',
                    used_order_id = ?,
                    used_at = ?
                WHERE coupon_id = ?
                  AND user_id = ?
                  AND status = ?
                """,
                (
                    order.order_id,
                    confirmed_at_text,
                    order.coupon_id,
                    str(order.user_id),
                    COUPON_STATUS_AVAILABLE,
                ),
            )
            if int(coupon_update.rowcount or 0) != 1:
                raise PreconditionFailure("membership order coupon is unavailable")

        self._grant_invite_reward_locked(
            conn,
            order=order,
            confirmed_at=confirmed_at_text,
            confirmed_at_dt=confirmed_at_dt,
        )
        refreshed_order_row = conn.execute(
            "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
            (order.order_id,),
        ).fetchone()
        if refreshed_order_row is None:
            raise NotFound("membership order")
        conn.commit()
        membership = self._summary_from_conn(conn, str(order.user_id))
        return MembershipPaymentConfirmation(
            order=self._row_to_order(refreshed_order_row),
            membership=membership,
            payment_id=payment_id,
            idempotent=False,
        )

    def confirm_payment(
        self,
        user_id: str,
        *,
        provider: str,
        order_id: str,
        provider_trade_no: str | None = None,
    ) -> MembershipPaymentConfirmation:
        normalized_provider = _normalize_provider(provider)
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        default_trade_no = f"manual_{normalized_order_id}" if normalized_provider == PAYMENT_PROVIDER_MANUAL_TEST else normalized_order_id
        resolved_provider_trade_no = str(provider_trade_no or default_trade_no).strip()
        callback_payload_json = json.dumps(
            {
                "orderId": normalized_order_id,
                "provider": normalized_provider,
                "providerTradeNo": resolved_provider_trade_no,
                "userId": str(user_id),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        now = _utc_now()
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, user_id=str(user_id), now=now)
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? AND user_id = ? LIMIT 1",
                    (normalized_order_id, str(user_id)),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(row)
                if order.provider != normalized_provider:
                    raise PreconditionFailure("membership payment provider does not match the order provider")
                return self._confirm_payment_locked(
                    conn,
                    order,
                    provider_trade_no=resolved_provider_trade_no,
                    confirmed_at=now.isoformat(),
                    callback_payload_json=callback_payload_json,
                )
            finally:
                conn.close()

    def confirm_provider_payment(
        self,
        *,
        order_id: str,
        provider: str,
        provider_trade_no: str,
        amount_cent: int | None = None,
        paid_at: str | None = None,
        payer_id: str | None = None,
        callback_payload_json: str = "",
    ) -> MembershipPaymentConfirmation:
        normalized_provider = _normalize_provider(provider)
        normalized_order_id = str(order_id).strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        resolved_provider_trade_no = str(provider_trade_no or "").strip()
        if not resolved_provider_trade_no:
            raise PreconditionFailure("membership providerTradeNo must be non-empty")
        resolved_paid_at = paid_at or _utc_now().isoformat()

        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, now=_parse_dt(resolved_paid_at))
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(row)
                if order.provider != normalized_provider:
                    raise PreconditionFailure("membership payment provider does not match the order provider")
                if amount_cent is not None and int(amount_cent) != order.payable_amount_cent:
                    raise PreconditionFailure("membership payment amount does not match the order")
                return self._confirm_payment_locked(
                    conn,
                    order,
                    provider_trade_no=resolved_provider_trade_no,
                    confirmed_at=resolved_paid_at,
                    callback_payload_json=callback_payload_json,
                    provider_buyer_id=payer_id,
                )
            finally:
                conn.close()

    def _finalize_refund_locked(
        self,
        conn: sqlite3.Connection,
        order: MembershipOrder,
        *,
        reason: str,
        now: datetime,
        refund_payload_json: str = "",
        provider_refund_no: str | None = None,
    ) -> MembershipRefundResult:
        normalized_reason = str(reason or "").strip() or "membership order refunded by administrator"
        now_text = now.isoformat()
        if order.status == "refunded":
            self._rebuild_user_entitlements(
                conn,
                order.user_id,
                now=now,
                revoked_reason=normalized_reason,
            )
            membership = self._summary_from_conn(conn, order.user_id)
            conn.commit()
            return MembershipRefundResult(
                order=order,
                membership=membership,
                idempotent=True,
                restored_coupon_id=None,
                restored_coupon_status=None,
                revoked_reward_coupon_id=None,
                completed=True,
                refund_request_submitted=False,
                remote_status="refunded",
                provider_refund_no=provider_refund_no,
            )
        if order.status not in {"paid", "refund_pending"}:
            raise PreconditionFailure("only paid or refund_pending membership orders can be refunded")

        restored_coupon_id, restored_coupon_status = self._restore_coupon_after_refund(conn, order, now=now)
        self._ensure_commission_tables(conn)
        conn.execute(
            """
            UPDATE commission_records
            SET status = 'canceled',
                canceled_at = ?,
                cancel_reason = ?
            WHERE source_order_id = ?
              AND status = 'pending'
            """,
            (now_text, normalized_reason, order.order_id),
        )
        conn.execute(
            """
            UPDATE invite_bindings
            SET status = ?,
                reward_trigger_order_id = CASE
                    WHEN reward_trigger_order_id = ? THEN NULL
                    ELSE reward_trigger_order_id
                END
            WHERE invitee_user_id = ?
              AND status = ?
            """,
            (
                INVITE_BINDING_STATUS_BOUND,
                order.order_id,
                str(order.user_id),
                INVITE_BINDING_STATUS_COMMISSION_PENDING,
            ),
        )
        revoked_reward_coupon_id = self._rollback_invite_reward_for_refund(
            conn,
            order,
            now=now,
            reason=normalized_reason,
        )
        payment_updates: list[object] = ["refunded", now_text]
        payment_sql = """
            UPDATE membership_payments
            SET status = ?,
                refunded_at = ?,
                refund_callback_payload_json = CASE
                    WHEN ? != '' THEN ?
                    ELSE refund_callback_payload_json
                END
        """
        payment_updates.extend([str(refund_payload_json or ""), str(refund_payload_json or "")])
        if provider_refund_no:
            payment_sql += ", refund_out_refund_no = ?"
            payment_updates.append(str(provider_refund_no))
        payment_sql += """
            WHERE order_id = ?
              AND status != 'refunded'
        """
        payment_updates.append(order.order_id)
        conn.execute(payment_sql, tuple(payment_updates))
        conn.execute(
            """
            UPDATE membership_orders
            SET status = 'refunded',
                refunded_at = ?
            WHERE order_id = ?
            """,
            (now_text, order.order_id),
        )
        self._rebuild_user_entitlements(
            conn,
            order.user_id,
            now=now,
            revoked_reason=normalized_reason,
        )
        refreshed_order_row = conn.execute(
            "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
            (order.order_id,),
        ).fetchone()
        if refreshed_order_row is None:
            raise NotFound("membership order")
        membership = self._summary_from_conn(conn, order.user_id)
        conn.commit()
        return MembershipRefundResult(
            order=self._row_to_order(refreshed_order_row),
            membership=membership,
            idempotent=False,
            restored_coupon_id=restored_coupon_id,
            restored_coupon_status=restored_coupon_status,
            revoked_reward_coupon_id=revoked_reward_coupon_id,
            completed=True,
            refund_request_submitted=False,
            remote_status="refunded",
            provider_refund_no=provider_refund_no,
        )

    def mark_refund_pending(
        self,
        *,
        order_id: str,
        provider: str,
        refund_out_refund_no: str,
        refund_payload_json: str = "",
        requested_at: str | None = None,
    ) -> MembershipRefundResult:
        normalized_order_id = str(order_id or "").strip()
        normalized_provider = _normalize_provider(provider)
        normalized_refund_out_refund_no = str(refund_out_refund_no or "").strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        if not normalized_refund_out_refund_no:
            raise PreconditionFailure("membership refund out_refund_no must be non-empty")
        requested_at_text = requested_at or _utc_now().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, now=_parse_dt(requested_at_text))
                order_row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if order_row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(order_row)
                if order.provider != normalized_provider:
                    raise PreconditionFailure("membership payment provider does not match the order provider")
                if order.status == "refunded":
                    membership = self._summary_from_conn(conn, order.user_id)
                    return MembershipRefundResult(
                        order=order,
                        membership=membership,
                        idempotent=True,
                        restored_coupon_id=None,
                        restored_coupon_status=None,
                        revoked_reward_coupon_id=None,
                        completed=True,
                        refund_request_submitted=False,
                        remote_status="refunded",
                        provider_refund_no=normalized_refund_out_refund_no,
                    )
                if order.status not in {"paid", "refund_pending"}:
                    raise PreconditionFailure("only paid or refund_pending membership orders can enter refund_pending")
                self._ensure_refund_window_open(order, now=_parse_dt(requested_at_text))
                payment_row = self._latest_payment_row_for_order(conn, order.order_id)
                if payment_row is None:
                    raise NotFound("membership payment")
                payment = self._row_to_payment(payment_row)
                if payment.provider != normalized_provider:
                    raise PreconditionFailure("membership payment provider does not match the order provider")
                conn.execute(
                    """
                    UPDATE membership_payments
                    SET status = 'refund_pending',
                        refund_out_refund_no = ?,
                        refund_requested_at = ?,
                        refund_callback_payload_json = CASE
                            WHEN ? != '' THEN ?
                            ELSE refund_callback_payload_json
                        END
                    WHERE payment_id = ?
                    """,
                    (
                        normalized_refund_out_refund_no,
                        requested_at_text,
                        str(refund_payload_json or ""),
                        str(refund_payload_json or ""),
                        payment.payment_id,
                    ),
                )
                conn.execute(
                    "UPDATE membership_orders SET status = 'refund_pending' WHERE order_id = ?",
                    (order.order_id,),
                )
                refreshed_order_row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (order.order_id,),
                ).fetchone()
                if refreshed_order_row is None:
                    raise NotFound("membership order")
                membership = self._summary_from_conn(conn, order.user_id)
                conn.commit()
                return MembershipRefundResult(
                    order=self._row_to_order(refreshed_order_row),
                    membership=membership,
                    idempotent=order.status == "refund_pending" and payment.refund_out_refund_no == normalized_refund_out_refund_no,
                    restored_coupon_id=None,
                    restored_coupon_status=None,
                    revoked_reward_coupon_id=None,
                    completed=False,
                    refund_request_submitted=True,
                    remote_status="refund_pending",
                    provider_refund_no=normalized_refund_out_refund_no,
                )
            finally:
                conn.close()

    def sync_provider_refund(
        self,
        *,
        order_id: str,
        provider: str,
        refund_out_refund_no: str,
        remote_status: str,
        refund_payload_json: str = "",
        refunded_at: str | None = None,
        reason: str = "",
    ) -> MembershipRefundResult:
        normalized_order_id = str(order_id or "").strip()
        normalized_provider = _normalize_provider(provider)
        normalized_refund_out_refund_no = str(refund_out_refund_no or "").strip()
        normalized_remote_status = str(remote_status or "").strip().lower() or "unknown"
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        if not normalized_refund_out_refund_no:
            raise PreconditionFailure("membership refund out_refund_no must be non-empty")

        with self._lock:
            conn = self._connect()
            try:
                order_row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if order_row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(order_row)
                if order.provider != normalized_provider:
                    raise PreconditionFailure("membership payment provider does not match the order provider")
                payment_row = self._latest_payment_row_for_order(conn, order.order_id)
                if payment_row is None:
                    raise NotFound("membership payment")
                payment = self._row_to_payment(payment_row)
                if normalized_remote_status == "refunded":
                    effective_refunded_at = refunded_at or _utc_now().isoformat()
                    return self._finalize_refund_locked(
                        conn,
                        order,
                        reason=reason,
                        now=_parse_dt(effective_refunded_at),
                        refund_payload_json=refund_payload_json,
                        provider_refund_no=normalized_refund_out_refund_no,
                    )
                if normalized_remote_status == "refund_pending":
                    conn.execute(
                        """
                        UPDATE membership_payments
                        SET status = 'refund_pending',
                            refund_out_refund_no = ?,
                            refund_requested_at = COALESCE(refund_requested_at, ?),
                            refund_callback_payload_json = CASE
                                WHEN ? != '' THEN ?
                                ELSE refund_callback_payload_json
                            END
                        WHERE payment_id = ?
                        """,
                        (
                            normalized_refund_out_refund_no,
                            _utc_now().isoformat(),
                            str(refund_payload_json or ""),
                            str(refund_payload_json or ""),
                            payment.payment_id,
                        ),
                    )
                    conn.execute(
                        "UPDATE membership_orders SET status = 'refund_pending' WHERE order_id = ?",
                        (order.order_id,),
                    )
                    refreshed_order_row = conn.execute(
                        "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                        (order.order_id,),
                    ).fetchone()
                    if refreshed_order_row is None:
                        raise NotFound("membership order")
                    membership = self._summary_from_conn(conn, order.user_id)
                    conn.commit()
                    return MembershipRefundResult(
                        order=self._row_to_order(refreshed_order_row),
                        membership=membership,
                        idempotent=order.status == "refund_pending" and payment.refund_out_refund_no == normalized_refund_out_refund_no,
                        restored_coupon_id=None,
                        restored_coupon_status=None,
                        revoked_reward_coupon_id=None,
                        completed=False,
                        refund_request_submitted=False,
                        remote_status="refund_pending",
                        provider_refund_no=normalized_refund_out_refund_no,
                    )
                if normalized_remote_status == "failed":
                    conn.execute(
                        """
                        UPDATE membership_payments
                        SET status = 'succeeded',
                            refund_out_refund_no = ?,
                            refund_callback_payload_json = CASE
                                WHEN ? != '' THEN ?
                                ELSE refund_callback_payload_json
                            END
                        WHERE payment_id = ?
                        """,
                        (
                            normalized_refund_out_refund_no,
                            str(refund_payload_json or ""),
                            str(refund_payload_json or ""),
                            payment.payment_id,
                        ),
                    )
                    conn.execute(
                        "UPDATE membership_orders SET status = 'paid' WHERE order_id = ?",
                        (order.order_id,),
                    )
                    refreshed_order_row = conn.execute(
                        "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                        (order.order_id,),
                    ).fetchone()
                    if refreshed_order_row is None:
                        raise NotFound("membership order")
                    membership = self._summary_from_conn(conn, order.user_id)
                    conn.commit()
                    return MembershipRefundResult(
                        order=self._row_to_order(refreshed_order_row),
                        membership=membership,
                        idempotent=False,
                        restored_coupon_id=None,
                        restored_coupon_status=None,
                        revoked_reward_coupon_id=None,
                        completed=False,
                        refund_request_submitted=False,
                        remote_status="failed",
                        provider_refund_no=normalized_refund_out_refund_no,
                    )
                raise PreconditionFailure(f"membership refund remote status is unsupported: {normalized_remote_status}")
            finally:
                conn.close()

    def refund_order(self, order_id: str, *, reason: str = "") -> MembershipRefundResult:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            raise PreconditionFailure("membership orderId must be non-empty")
        normalized_reason = str(reason or "").strip() or "membership order refunded by administrator"
        now = _utc_now()
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_rows(conn, now=now)
                row = conn.execute(
                    "SELECT * FROM membership_orders WHERE order_id = ? LIMIT 1",
                    (normalized_order_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("membership order")
                order = self._row_to_order(row)
                self._ensure_refund_window_open(order, now=now)
                return self._finalize_refund_locked(
                    conn,
                    order,
                    reason=normalized_reason,
                    now=now,
                )
            finally:
                conn.close()
