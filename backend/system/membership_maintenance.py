from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from backend.system.membership_payment_service import PAYMENT_PROVIDER_WECHAT_NATIVE, MembershipPaymentService
from backend.system.membership_store import MembershipStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _env_int(name: str, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except Exception:
        return default
    return max(minimum, min(value, maximum))


@dataclass(frozen=True, slots=True)
class MembershipPendingPaymentReconcileConfig:
    min_age_minutes: int
    limit: int


@dataclass(frozen=True, slots=True)
class MembershipPendingPaymentReconcileItem:
    order_id: str
    user_id: str
    provider: str
    previous_status: str
    current_status: str | None
    remote_status: str | None
    provider_trade_no: str | None
    action: str
    error: str | None


@dataclass(frozen=True, slots=True)
class MembershipPendingPaymentReconcileSummary:
    provider: str
    min_age_minutes: int
    limit: int
    started_at: str
    finished_at: str
    scanned_count: int
    confirmed_count: int
    closed_count: int
    pending_count: int
    error_count: int
    items: tuple[MembershipPendingPaymentReconcileItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "minAgeMinutes": self.min_age_minutes,
            "limit": self.limit,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "scannedCount": self.scanned_count,
            "confirmedCount": self.confirmed_count,
            "closedCount": self.closed_count,
            "pendingCount": self.pending_count,
            "errorCount": self.error_count,
            "items": [asdict(item) for item in self.items],
        }


def current_membership_pending_payment_reconcile_config() -> MembershipPendingPaymentReconcileConfig:
    return MembershipPendingPaymentReconcileConfig(
        min_age_minutes=_env_int("PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_MIN_AGE_MINUTES", 5, minimum=0, maximum=24 * 60),
        limit=_env_int("PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_LIMIT", 100, minimum=1, maximum=500),
    )


def reconcile_pending_wechat_membership_payments(
    membership_store: MembershipStore,
    membership_payment_service: MembershipPaymentService,
    *,
    min_age_minutes: int,
    limit: int,
    now: datetime | None = None,
) -> MembershipPendingPaymentReconcileSummary:
    started = now or _utc_now()
    candidates = membership_store.list_pending_payment_sync_candidates(
        provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
        older_than_minutes=min_age_minutes,
        limit=limit,
        now=started,
    )

    items: list[MembershipPendingPaymentReconcileItem] = []
    confirmed_count = 0
    closed_count = 0
    pending_count = 0
    error_count = 0

    for order in candidates:
        try:
            remote_status = membership_payment_service.query_payment_status(order)
            synced = membership_store.sync_provider_payment_status(order_id=order.order_id, remote_status=remote_status)
            if synced.confirmed:
                confirmed_count += 1
                action = "confirmed_paid"
            elif synced.order.status == "closed":
                closed_count += 1
                action = f"closed_{remote_status.remote_status}"
            else:
                pending_count += 1
                action = f"kept_{remote_status.remote_status}"
            items.append(
                MembershipPendingPaymentReconcileItem(
                    order_id=order.order_id,
                    user_id=order.user_id,
                    provider=order.provider,
                    previous_status=order.status,
                    current_status=synced.order.status,
                    remote_status=remote_status.remote_status,
                    provider_trade_no=remote_status.provider_trade_no or synced.order.provider_trade_no,
                    action=action,
                    error=None,
                )
            )
        except Exception as exc:
            error_count += 1
            items.append(
                MembershipPendingPaymentReconcileItem(
                    order_id=order.order_id,
                    user_id=order.user_id,
                    provider=order.provider,
                    previous_status=order.status,
                    current_status=None,
                    remote_status=None,
                    provider_trade_no=order.provider_trade_no,
                    action="error",
                    error=str(exc),
                )
            )

    finished = _utc_now()
    return MembershipPendingPaymentReconcileSummary(
        provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
        min_age_minutes=max(0, int(min_age_minutes)),
        limit=max(1, int(limit)),
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        scanned_count=len(candidates),
        confirmed_count=confirmed_count,
        closed_count=closed_count,
        pending_count=pending_count,
        error_count=error_count,
        items=tuple(items),
    )
