import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.models.errors import NotFound, PreconditionFailure
from backend.system.app_paths import resolve_membership_db_path

INVITE_BINDING_STATUS_BOUND = "bound"
INVITE_BINDING_STATUS_DISCOUNT_ISSUED = "discount_issued"
INVITE_BINDING_STATUS_COMMISSION_PENDING = "commission_pending"
INVITE_BINDING_STATUS_COMMISSION_SETTLED = "commission_settled"
INVITE_BINDING_STATUS_REWARDED = "rewarded"
COUPON_STATUS_AVAILABLE = "available"
COUPON_STATUS_USED = "used"
COUPON_STATUS_REVOKED = "revoked"
COUPON_STATUS_EXPIRED = "expired"
COUPON_TYPE_CASH = "cash"
COUPON_TYPE_PERCENT = "percent"
REWARD_STATUS_ISSUED = "issued"
REWARD_STATUS_REVOKED = "revoked"
INVITE_REWARD_SOURCE = "invite_reward"
INVITE_DISCOUNT_SOURCE = "invite_discount"
ADMIN_GRANT_COUPON_SOURCE = "admin_grant"
INVITE_REWARD_COUPON_TITLE = "邀请奖励 5 元券"
INVITE_REWARD_COUPON_AMOUNT_CENT = 500
INVITE_REWARD_COUPON_MIN_SPEND_CENT = 1490
INVITE_REWARD_COUPON_EXPIRE_DAYS = 30
INVITE_DISCOUNT_COUPON_TITLE = "邀请码 7.5 折券"
INVITE_DISCOUNT_RATE = 75
INVITE_DISCOUNT_EXPIRE_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_limit(limit: int, *, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, maximum))


def _normalize_coupon_status_filter(status: str | None) -> str | None:
    value = str(status or "").strip().lower()
    if not value or value == "all":
        return None
    if value not in {COUPON_STATUS_AVAILABLE, COUPON_STATUS_USED, COUPON_STATUS_REVOKED, COUPON_STATUS_EXPIRED}:
        raise PreconditionFailure("coupon status must be one of available, used, revoked, expired, all")
    return value


def _normalize_invite_status_filter(status: str | None) -> str | None:
    value = str(status or "").strip().lower()
    if not value or value == "all":
        return None
    if value not in {
        INVITE_BINDING_STATUS_BOUND,
        INVITE_BINDING_STATUS_DISCOUNT_ISSUED,
        INVITE_BINDING_STATUS_COMMISSION_PENDING,
        INVITE_BINDING_STATUS_COMMISSION_SETTLED,
        INVITE_BINDING_STATUS_REWARDED,
    }:
        raise PreconditionFailure("invite status must be one of bound, discount_issued, commission_pending, commission_settled, rewarded, all")
    return value


@dataclass(frozen=True, slots=True)
class InviteBinding:
    invitee_user_id: str
    inviter_user_id: str
    invite_code_snapshot: str
    status: str
    bound_at: str
    rewarded_at: str | None
    reward_trigger_order_id: str | None
    reward_coupon_id: str | None
    discount_coupon_id: str | None


@dataclass(frozen=True, slots=True)
class CouponRecord:
    coupon_id: str
    user_id: str
    title: str
    coupon_type: str
    discount_rate: int | None
    amount_cent: int
    min_spend_cent: int
    source: str
    status: str
    source_invitee_user_id: str | None
    created_at: str
    expires_at: str | None
    used_at: str | None
    used_order_id: str | None


@dataclass(frozen=True, slots=True)
class InviteSummary:
    user_id: str
    invite_code: str
    bound_inviter_user_id: str | None
    bound_invite_code: str | None
    binding_status: str | None
    bound_at: str | None
    total_invited_users: int
    rewarded_invite_count: int
    available_coupon_count: int
    pending_commission_cent: int
    withdrawable_commission_cent: int


@dataclass(frozen=True, slots=True)
class MembershipMarketingAdminOverview:
    invite_bindings_count: int
    rewarded_invite_count: int
    coupon_count: int
    available_coupon_count: int
    used_coupon_count: int


@dataclass(frozen=True, slots=True)
class InviteReferralRecord:
    invitee_user_id: str
    status: str
    bound_at: str
    rewarded_at: str | None
    reward_trigger_order_id: str | None
    reward_coupon_id: str | None
    discount_coupon_id: str | None
    commission_amount_cent: int | None


class MembershipMarketingStore:
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
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if any(str(row["name"]) == str(column_name) for row in columns):
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    @staticmethod
    def _table_sql(conn: sqlite3.Connection, table_name: str) -> str:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (str(table_name),),
        ).fetchone()
        return "" if row is None or row["sql"] is None else str(row["sql"])

    def _ensure_invite_binding_constraints(self, conn: sqlite3.Connection) -> None:
        schema_sql = self._table_sql(conn, "invite_bindings")
        required_statuses = {
            INVITE_BINDING_STATUS_BOUND,
            INVITE_BINDING_STATUS_DISCOUNT_ISSUED,
            INVITE_BINDING_STATUS_COMMISSION_PENDING,
            INVITE_BINDING_STATUS_COMMISSION_SETTLED,
            INVITE_BINDING_STATUS_REWARDED,
        }
        present_statuses = {required_status for required_status in required_statuses if required_status in schema_sql}
        if schema_sql and required_statuses <= present_statuses:
            return

        conn.executescript(
            f"""
            DROP TABLE IF EXISTS invite_bindings_next;

            CREATE TABLE invite_bindings_next (
                invitee_user_id TEXT PRIMARY KEY,
                inviter_user_id TEXT NOT NULL,
                invite_code_snapshot TEXT NOT NULL,
                status TEXT NOT NULL,
                bound_at TEXT NOT NULL,
                rewarded_at TEXT,
                reward_trigger_order_id TEXT,
                reward_coupon_id TEXT,
                discount_coupon_id TEXT,
                CHECK (status IN ('{INVITE_BINDING_STATUS_BOUND}', '{INVITE_BINDING_STATUS_DISCOUNT_ISSUED}', '{INVITE_BINDING_STATUS_COMMISSION_PENDING}', '{INVITE_BINDING_STATUS_COMMISSION_SETTLED}', '{INVITE_BINDING_STATUS_REWARDED}'))
            );
            """
        )
        conn.execute(
            f"""
            INSERT INTO invite_bindings_next (
                invitee_user_id,
                inviter_user_id,
                invite_code_snapshot,
                status,
                bound_at,
                rewarded_at,
                reward_trigger_order_id,
                reward_coupon_id,
                discount_coupon_id
            )
            SELECT
                invitee_user_id,
                inviter_user_id,
                invite_code_snapshot,
                CASE
                    WHEN status IN (?, ?, ?, ?, ?) THEN status
                    ELSE ?
                END,
                bound_at,
                rewarded_at,
                reward_trigger_order_id,
                reward_coupon_id,
                discount_coupon_id
            FROM invite_bindings
            """,
            (
                INVITE_BINDING_STATUS_BOUND,
                INVITE_BINDING_STATUS_DISCOUNT_ISSUED,
                INVITE_BINDING_STATUS_COMMISSION_PENDING,
                INVITE_BINDING_STATUS_COMMISSION_SETTLED,
                INVITE_BINDING_STATUS_REWARDED,
                INVITE_BINDING_STATUS_BOUND,
            ),
        )
        conn.execute("DROP TABLE invite_bindings")
        conn.execute("ALTER TABLE invite_bindings_next RENAME TO invite_bindings")

    def _ensure_coupon_constraints(self, conn: sqlite3.Connection) -> None:
        schema_sql = self._table_sql(conn, "coupons")
        if "amount_cent >= 0" in schema_sql and COUPON_TYPE_PERCENT in schema_sql:
            return

        conn.executescript(
            f"""
            DROP TABLE IF EXISTS coupons_next;

            CREATE TABLE coupons_next (
                coupon_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                coupon_type TEXT NOT NULL DEFAULT '{COUPON_TYPE_CASH}',
                discount_rate INTEGER,
                amount_cent INTEGER NOT NULL,
                min_spend_cent INTEGER NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                source_invitee_user_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                used_at TEXT,
                used_order_id TEXT,
                revoked_at TEXT,
                revoke_reason TEXT NOT NULL DEFAULT '',
                CHECK (amount_cent >= 0),
                CHECK (coupon_type IN ('{COUPON_TYPE_CASH}', '{COUPON_TYPE_PERCENT}')),
                CHECK (discount_rate IS NULL OR (discount_rate > 0 AND discount_rate <= 100)),
                CHECK (min_spend_cent >= 0),
                CHECK (status IN ('{COUPON_STATUS_AVAILABLE}', '{COUPON_STATUS_USED}', '{COUPON_STATUS_REVOKED}', '{COUPON_STATUS_EXPIRED}'))
            );
            """
        )
        conn.execute(
            f"""
            INSERT INTO coupons_next (
                coupon_id,
                user_id,
                title,
                coupon_type,
                discount_rate,
                amount_cent,
                min_spend_cent,
                source,
                status,
                source_invitee_user_id,
                created_at,
                expires_at,
                used_at,
                used_order_id,
                revoked_at,
                revoke_reason
            )
            SELECT
                coupon_id,
                user_id,
                COALESCE(title, ''),
                CASE WHEN coupon_type IN (?, ?) THEN coupon_type ELSE ? END,
                discount_rate,
                amount_cent,
                min_spend_cent,
                source,
                CASE WHEN status IN (?, ?, ?, ?) THEN status ELSE ? END,
                source_invitee_user_id,
                created_at,
                expires_at,
                used_at,
                used_order_id,
                revoked_at,
                COALESCE(revoke_reason, '')
            FROM coupons
            """,
            (
                COUPON_TYPE_CASH,
                COUPON_TYPE_PERCENT,
                COUPON_TYPE_CASH,
                COUPON_STATUS_AVAILABLE,
                COUPON_STATUS_USED,
                COUPON_STATUS_REVOKED,
                COUPON_STATUS_EXPIRED,
                COUPON_STATUS_AVAILABLE,
            ),
        )
        conn.execute("DROP TABLE coupons")
        conn.execute("ALTER TABLE coupons_next RENAME TO coupons")

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    f"""
                    CREATE TABLE IF NOT EXISTS invite_bindings (
                        invitee_user_id TEXT PRIMARY KEY,
                        inviter_user_id TEXT NOT NULL,
                        invite_code_snapshot TEXT NOT NULL,
                        status TEXT NOT NULL,
                        bound_at TEXT NOT NULL,
                        rewarded_at TEXT,
                        reward_trigger_order_id TEXT,
                        reward_coupon_id TEXT,
                        discount_coupon_id TEXT,
                        CHECK (status IN ('{INVITE_BINDING_STATUS_BOUND}', '{INVITE_BINDING_STATUS_DISCOUNT_ISSUED}', '{INVITE_BINDING_STATUS_COMMISSION_PENDING}', '{INVITE_BINDING_STATUS_COMMISSION_SETTLED}', '{INVITE_BINDING_STATUS_REWARDED}'))
                    );

                    CREATE TABLE IF NOT EXISTS coupons (
                        coupon_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT '',
                        coupon_type TEXT NOT NULL DEFAULT '{COUPON_TYPE_CASH}',
                        discount_rate INTEGER,
                        amount_cent INTEGER NOT NULL,
                        min_spend_cent INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        status TEXT NOT NULL,
                        source_invitee_user_id TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        used_at TEXT,
                        used_order_id TEXT,
                        revoked_at TEXT,
                        revoke_reason TEXT NOT NULL DEFAULT '',
                        CHECK (amount_cent >= 0),
                        CHECK (coupon_type IN ('{COUPON_TYPE_CASH}', '{COUPON_TYPE_PERCENT}')),
                        CHECK (discount_rate IS NULL OR (discount_rate > 0 AND discount_rate <= 100)),
                        CHECK (min_spend_cent >= 0),
                        CHECK (status IN ('{COUPON_STATUS_AVAILABLE}', '{COUPON_STATUS_USED}', '{COUPON_STATUS_REVOKED}', '{COUPON_STATUS_EXPIRED}'))
                    );

                    CREATE TABLE IF NOT EXISTS invite_reward_records (
                        reward_id TEXT PRIMARY KEY,
                        inviter_user_id TEXT NOT NULL,
                        invitee_user_id TEXT NOT NULL UNIQUE,
                        trigger_order_id TEXT NOT NULL UNIQUE,
                        coupon_id TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        revoked_at TEXT,
                        CHECK (status IN ('{REWARD_STATUS_ISSUED}', '{REWARD_STATUS_REVOKED}'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_invite_bindings_inviter
                    ON invite_bindings (inviter_user_id, bound_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_coupons_user_status
                    ON coupons (user_id, status, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_invite_reward_records_inviter
                    ON invite_reward_records (inviter_user_id, created_at DESC);
                    """
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "title",
                    "title TEXT NOT NULL DEFAULT ''",
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "coupon_type",
                    f"coupon_type TEXT NOT NULL DEFAULT '{COUPON_TYPE_CASH}'",
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "discount_rate",
                    "discount_rate INTEGER",
                )
                self._ensure_column(
                    conn,
                    "invite_bindings",
                    "discount_coupon_id",
                    "discount_coupon_id TEXT",
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "source_invitee_user_id",
                    "source_invitee_user_id TEXT",
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "revoked_at",
                    "revoked_at TEXT",
                )
                self._ensure_column(
                    conn,
                    "coupons",
                    "revoke_reason",
                    "revoke_reason TEXT NOT NULL DEFAULT ''",
                )
                self._ensure_invite_binding_constraints(conn)
                self._ensure_coupon_constraints(conn)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_invite_bindings_inviter ON invite_bindings (inviter_user_id, bound_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_coupons_user_status ON coupons (user_id, status, created_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_invite_reward_records_inviter ON invite_reward_records (inviter_user_id, created_at DESC)"
                )
                conn.commit()
            finally:
                conn.close()

    def _sync_expired_coupons(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        now_text = (now or _utc_now()).isoformat()
        params: list[object] = [now_text]
        user_filter = ""
        if user_id:
            user_filter = " AND user_id = ?"
            params.append(str(user_id))
        conn.execute(
            f"""
            UPDATE coupons
            SET status = '{COUPON_STATUS_EXPIRED}'
            WHERE status = '{COUPON_STATUS_AVAILABLE}'
              AND expires_at IS NOT NULL
              AND expires_at <= ?{user_filter}
            """,
            tuple(params),
        )

    def _row_to_binding(self, row: sqlite3.Row) -> InviteBinding:
        return InviteBinding(
            invitee_user_id=str(row["invitee_user_id"]),
            inviter_user_id=str(row["inviter_user_id"]),
            invite_code_snapshot=str(row["invite_code_snapshot"]),
            status=str(row["status"]),
            bound_at=str(row["bound_at"]),
            rewarded_at=None if row["rewarded_at"] is None else str(row["rewarded_at"]),
            reward_trigger_order_id=None if row["reward_trigger_order_id"] is None else str(row["reward_trigger_order_id"]),
            reward_coupon_id=None if row["reward_coupon_id"] is None else str(row["reward_coupon_id"]),
            discount_coupon_id=None if row["discount_coupon_id"] is None else str(row["discount_coupon_id"]),
        )

    def _row_to_coupon(self, row: sqlite3.Row) -> CouponRecord:
        return CouponRecord(
            coupon_id=str(row["coupon_id"]),
            user_id=str(row["user_id"]),
            title=str(row["title"] or ""),
            coupon_type=str(row["coupon_type"] or COUPON_TYPE_CASH),
            discount_rate=None if row["discount_rate"] is None else int(row["discount_rate"]),
            amount_cent=int(row["amount_cent"]),
            min_spend_cent=int(row["min_spend_cent"]),
            source=str(row["source"]),
            status=str(row["status"]),
            source_invitee_user_id=None if row["source_invitee_user_id"] is None else str(row["source_invitee_user_id"]),
            created_at=str(row["created_at"]),
            expires_at=None if row["expires_at"] is None else str(row["expires_at"]),
            used_at=None if row["used_at"] is None else str(row["used_at"]),
            used_order_id=None if row["used_order_id"] is None else str(row["used_order_id"]),
        )

    def get_invite_binding(self, invitee_user_id: str) -> InviteBinding | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM invite_bindings WHERE invitee_user_id = ? LIMIT 1",
                (str(invitee_user_id),),
            ).fetchone()
            return None if row is None else self._row_to_binding(row)
        finally:
            conn.close()

    def get_coupon(self, coupon_id: str) -> CouponRecord | None:
        normalized_coupon_id = str(coupon_id or "").strip()
        if not normalized_coupon_id:
            return None
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn)
            row = conn.execute(
                "SELECT * FROM coupons WHERE coupon_id = ? LIMIT 1",
                (normalized_coupon_id,),
            ).fetchone()
            return None if row is None else self._row_to_coupon(row)
        finally:
            conn.close()

    def bind_invite_code(self, invitee_user_id: str, *, inviter_user_id: str, invite_code_snapshot: str) -> InviteBinding:
        normalized_invitee_user_id = str(invitee_user_id).strip()
        normalized_inviter_user_id = str(inviter_user_id).strip()
        normalized_invite_code = str(invite_code_snapshot).strip().upper()
        if not normalized_invitee_user_id or not normalized_inviter_user_id:
            raise PreconditionFailure("invite binding requires both inviter and invitee")
        if normalized_invitee_user_id == normalized_inviter_user_id:
            raise PreconditionFailure("you cannot use your own invite code")
        if not normalized_invite_code:
            raise PreconditionFailure("invite code must be non-empty")

        now_dt = _utc_now()
        now = now_dt.isoformat()
        discount_coupon_id = f"mcpn_{uuid.uuid4().hex}"
        discount_expires_at = (now_dt + timedelta(days=INVITE_DISCOUNT_EXPIRE_DAYS)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                paid_order = None
                if self._table_exists(conn, "membership_orders"):
                    paid_order = conn.execute(
                        "SELECT 1 FROM membership_orders WHERE user_id = ? AND status = 'paid' LIMIT 1",
                        (normalized_invitee_user_id,),
                    ).fetchone()
                if paid_order is not None:
                    raise PreconditionFailure("invite code must be bound before the first paid membership order")

                existing = conn.execute(
                    "SELECT * FROM invite_bindings WHERE invitee_user_id = ? LIMIT 1",
                    (normalized_invitee_user_id,),
                ).fetchone()
                if existing is not None:
                    binding = self._row_to_binding(existing)
                    if binding.inviter_user_id == normalized_inviter_user_id:
                        return binding
                    raise PreconditionFailure("invite code has already been bound for this user")

                conn.execute(
                    """
                    INSERT INTO invite_bindings (
                        invitee_user_id,
                        inviter_user_id,
                        invite_code_snapshot,
                        status,
                        bound_at,
                        discount_coupon_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_invitee_user_id,
                        normalized_inviter_user_id,
                        normalized_invite_code,
                        INVITE_BINDING_STATUS_DISCOUNT_ISSUED,
                        now,
                        discount_coupon_id,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO coupons (
                        coupon_id,
                        user_id,
                        title,
                        coupon_type,
                        discount_rate,
                        amount_cent,
                        min_spend_cent,
                        source,
                        status,
                        source_invitee_user_id,
                        created_at,
                        expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        discount_coupon_id,
                        normalized_invitee_user_id,
                        INVITE_DISCOUNT_COUPON_TITLE,
                        COUPON_TYPE_PERCENT,
                        INVITE_DISCOUNT_RATE,
                        0,
                        0,
                        INVITE_DISCOUNT_SOURCE,
                        COUPON_STATUS_AVAILABLE,
                        normalized_invitee_user_id,
                        now,
                        discount_expires_at,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM invite_bindings WHERE invitee_user_id = ? LIMIT 1",
                    (normalized_invitee_user_id,),
                ).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("invite binding")
                return self._row_to_binding(row)
            finally:
                conn.close()

    def get_invite_summary(self, user_id: str, *, invite_code: str) -> InviteSummary:
        normalized_user_id = str(user_id).strip()
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn, user_id=normalized_user_id)
            binding_row = conn.execute(
                "SELECT * FROM invite_bindings WHERE invitee_user_id = ? LIMIT 1",
                (normalized_user_id,),
            ).fetchone()
            counts = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM invite_bindings WHERE inviter_user_id = ?) AS total_invited_users,
                    (SELECT COUNT(*) FROM invite_reward_records WHERE inviter_user_id = ? AND status = ?) AS rewarded_invite_count,
                    (SELECT COUNT(*) FROM coupons WHERE user_id = ? AND status = ?) AS available_coupon_count
                """,
                (
                    normalized_user_id,
                    normalized_user_id,
                    REWARD_STATUS_ISSUED,
                    normalized_user_id,
                    COUPON_STATUS_AVAILABLE,
                ),
            ).fetchone()
            binding = None if binding_row is None else self._row_to_binding(binding_row)
            pending_commission_cent = 0
            withdrawable_commission_cent = 0
            if self._table_exists(conn, "commission_records"):
                commission_counts = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN status = 'pending' THEN commission_amount_cent ELSE 0 END), 0) AS pending_commission_cent,
                        COALESCE(SUM(CASE WHEN status = 'settled' THEN commission_amount_cent ELSE 0 END), 0) AS settled_commission_cent
                    FROM commission_records
                    WHERE inviter_user_id = ?
                    """,
                    (normalized_user_id,),
                ).fetchone()
                if commission_counts is not None:
                    pending_commission_cent = int(commission_counts["pending_commission_cent"] or 0)
                    withdrawable_commission_cent = int(commission_counts["settled_commission_cent"] or 0)
            return InviteSummary(
                user_id=normalized_user_id,
                invite_code=str(invite_code).strip().upper(),
                bound_inviter_user_id=None if binding is None else binding.inviter_user_id,
                bound_invite_code=None if binding is None else binding.invite_code_snapshot,
                binding_status=None if binding is None else binding.status,
                bound_at=None if binding is None else binding.bound_at,
                total_invited_users=0 if counts is None else int(counts["total_invited_users"] or 0),
                rewarded_invite_count=0 if counts is None else int(counts["rewarded_invite_count"] or 0),
                available_coupon_count=0 if counts is None else int(counts["available_coupon_count"] or 0),
                pending_commission_cent=pending_commission_cent,
                withdrawable_commission_cent=withdrawable_commission_cent,
            )
        finally:
            conn.close()

    def get_admin_overview(self) -> MembershipMarketingAdminOverview:
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn)
            row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM invite_bindings) AS invite_bindings_count,
                    (SELECT COUNT(*) FROM invite_reward_records WHERE status = ?) AS rewarded_invite_count,
                    (SELECT COUNT(*) FROM coupons) AS coupon_count,
                    (SELECT COUNT(*) FROM coupons WHERE status = ?) AS available_coupon_count,
                    (SELECT COUNT(*) FROM coupons WHERE status = ?) AS used_coupon_count
                """,
                (REWARD_STATUS_ISSUED, COUPON_STATUS_AVAILABLE, COUPON_STATUS_USED),
            ).fetchone()
            return MembershipMarketingAdminOverview(
                invite_bindings_count=0 if row is None else int(row["invite_bindings_count"] or 0),
                rewarded_invite_count=0 if row is None else int(row["rewarded_invite_count"] or 0),
                coupon_count=0 if row is None else int(row["coupon_count"] or 0),
                available_coupon_count=0 if row is None else int(row["available_coupon_count"] or 0),
                used_coupon_count=0 if row is None else int(row["used_coupon_count"] or 0),
            )
        finally:
            conn.close()

    def list_recent_invites(self, inviter_user_id: str, *, limit: int = 10) -> tuple[InviteReferralRecord, ...]:
        normalized_limit = _normalize_limit(limit, default=10, maximum=50)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    invitee_user_id,
                    status,
                    bound_at,
                    rewarded_at,
                    reward_trigger_order_id,
                    reward_coupon_id,
                    discount_coupon_id
                FROM invite_bindings
                WHERE inviter_user_id = ?
                ORDER BY bound_at DESC, invitee_user_id DESC
                LIMIT ?
                """,
                (str(inviter_user_id), normalized_limit),
            ).fetchall()
            return tuple(
                InviteReferralRecord(
                    invitee_user_id=str(row["invitee_user_id"]),
                    status=str(row["status"]),
                    bound_at=str(row["bound_at"]),
                    rewarded_at=None if row["rewarded_at"] is None else str(row["rewarded_at"]),
                    reward_trigger_order_id=None if row["reward_trigger_order_id"] is None else str(row["reward_trigger_order_id"]),
                    reward_coupon_id=None if row["reward_coupon_id"] is None else str(row["reward_coupon_id"]),
                    discount_coupon_id=None if row["discount_coupon_id"] is None else str(row["discount_coupon_id"]),
                    commission_amount_cent=500 if str(row["status"] or "") == INVITE_BINDING_STATUS_COMMISSION_PENDING else None,
                )
                for row in rows
            )
        finally:
            conn.close()

    def list_admin_invites(self, *, status: str | None = None, limit: int = 100) -> tuple[InviteBinding, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        normalized_status = _normalize_invite_status_filter(status)
        params: list[object] = []
        where = ""
        if normalized_status:
            where = "WHERE status = ?"
            params.append(normalized_status)
        params.append(normalized_limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT *
                FROM invite_bindings
                {where}
                ORDER BY bound_at DESC, invitee_user_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_binding(row) for row in rows)
        finally:
            conn.close()

    def list_coupons(self, user_id: str, *, limit: int = 20) -> tuple[CouponRecord, ...]:
        normalized_limit = _normalize_limit(limit)
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn, user_id=str(user_id))
            rows = conn.execute(
                """
                SELECT *
                FROM coupons
                WHERE user_id = ?
                ORDER BY created_at DESC, coupon_id DESC
                LIMIT ?
                """,
                (str(user_id), normalized_limit),
            ).fetchall()
            return tuple(self._row_to_coupon(row) for row in rows)
        finally:
            conn.close()

    def list_admin_coupons(self, *, status: str | None = None, limit: int = 100) -> tuple[CouponRecord, ...]:
        normalized_limit = _normalize_limit(limit, default=100, maximum=200)
        normalized_status = _normalize_coupon_status_filter(status)
        params: list[object] = []
        where = ""
        if normalized_status:
            where = "WHERE status = ?"
            params.append(normalized_status)
        params.append(normalized_limit)
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn)
            rows = conn.execute(
                f"""
                SELECT *
                FROM coupons
                {where}
                ORDER BY created_at DESC, coupon_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return tuple(self._row_to_coupon(row) for row in rows)
        finally:
            conn.close()

    def resolve_coupon_discount(self, user_id: str, *, coupon_id: str | None, order_amount_cent: int) -> tuple[str | None, int]:
        normalized_coupon_id = str(coupon_id or "").strip()
        if not normalized_coupon_id:
            return None, 0
        normalized_user_id = str(user_id).strip()
        payable_before_coupon = max(0, int(order_amount_cent))
        conn = self._connect()
        try:
            self._sync_expired_coupons(conn, user_id=normalized_user_id)
            row = conn.execute(
                """
                SELECT *
                FROM coupons
                WHERE coupon_id = ?
                  AND user_id = ?
                LIMIT 1
                """,
                (normalized_coupon_id, normalized_user_id),
            ).fetchone()
            if row is None:
                raise NotFound("coupon")
            coupon = self._row_to_coupon(row)
            if coupon.status != COUPON_STATUS_AVAILABLE:
                raise PreconditionFailure("coupon is not available")
            if coupon.min_spend_cent > payable_before_coupon:
                raise PreconditionFailure("coupon does not meet the minimum spend")
            if coupon.coupon_type == COUPON_TYPE_PERCENT:
                discount_cent = max(0, payable_before_coupon - ((payable_before_coupon * int(coupon.discount_rate or 100)) // 100))
                return coupon.coupon_id, min(discount_cent, payable_before_coupon)
            return coupon.coupon_id, min(coupon.amount_cent, payable_before_coupon)
        finally:
            conn.close()

    def grant_coupon(
        self,
        user_id: str,
        *,
        amount_cent: int,
        title: str,
        expires_in_days: int,
        min_spend_cent: int = 0,
    ) -> CouponRecord:
        normalized_user_id = str(user_id).strip()
        normalized_title = str(title).strip()
        normalized_amount_cent = int(amount_cent)
        normalized_expires_in_days = int(expires_in_days)
        normalized_min_spend_cent = max(0, int(min_spend_cent))
        if not normalized_user_id:
            raise PreconditionFailure("coupon userId must be non-empty")
        if normalized_amount_cent <= 0:
            raise PreconditionFailure("coupon amount must be positive")
        if not normalized_title:
            raise PreconditionFailure("coupon title must be non-empty")
        if normalized_expires_in_days <= 0:
            raise PreconditionFailure("coupon expiresInDays must be positive")

        now = _utc_now()
        coupon_id = f"mcpn_{uuid.uuid4().hex}"
        created_at = now.isoformat()
        expires_at = (now + timedelta(days=normalized_expires_in_days)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO coupons (
                        coupon_id,
                        user_id,
                        title,
                        coupon_type,
                        discount_rate,
                        amount_cent,
                        min_spend_cent,
                        source,
                        status,
                        created_at,
                        expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        coupon_id,
                        normalized_user_id,
                        normalized_title,
                        COUPON_TYPE_CASH,
                        None,
                        normalized_amount_cent,
                        normalized_min_spend_cent,
                        ADMIN_GRANT_COUPON_SOURCE,
                        COUPON_STATUS_AVAILABLE,
                        created_at,
                        expires_at,
                    ),
                )
                row = conn.execute("SELECT * FROM coupons WHERE coupon_id = ? LIMIT 1", (coupon_id,)).fetchone()
                conn.commit()
                if row is None:
                    raise NotFound("coupon")
                return self._row_to_coupon(row)
            finally:
                conn.close()

    def void_coupon(self, coupon_id: str, *, reason: str = "") -> CouponRecord:
        normalized_coupon_id = str(coupon_id).strip()
        if not normalized_coupon_id:
            raise PreconditionFailure("couponId must be non-empty")
        normalized_reason = str(reason).strip()
        with self._lock:
            conn = self._connect()
            try:
                self._sync_expired_coupons(conn)
                row = conn.execute("SELECT * FROM coupons WHERE coupon_id = ? LIMIT 1", (normalized_coupon_id,)).fetchone()
                if row is None:
                    raise NotFound("coupon")
                coupon = self._row_to_coupon(row)
                if coupon.status == COUPON_STATUS_USED:
                    raise PreconditionFailure("used coupon cannot be voided")
                if coupon.status == COUPON_STATUS_REVOKED:
                    return coupon
                if coupon.status == COUPON_STATUS_EXPIRED:
                    raise PreconditionFailure("expired coupon cannot be voided")
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
                        _utc_now().isoformat(),
                        normalized_reason,
                        normalized_coupon_id,
                    ),
                )
                refreshed = conn.execute("SELECT * FROM coupons WHERE coupon_id = ? LIMIT 1", (normalized_coupon_id,)).fetchone()
                conn.commit()
                if refreshed is None:
                    raise NotFound("coupon")
                return self._row_to_coupon(refreshed)
            finally:
                conn.close()
