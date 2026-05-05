from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from backend.system.membership_commission_store import (
    WITHDRAWAL_STATUS_CANCELED,
    WITHDRAWAL_STATUS_FAILED,
    WITHDRAWAL_STATUS_NEEDS_ATTENTION,
    WITHDRAWAL_STATUS_SUCCEEDED,
    MembershipCommissionStore,
)
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


@dataclass(frozen=True, slots=True)
class CommissionSettlementMaintenanceSummary:
    run_id: str
    run_type: str
    started_at: str
    finished_at: str
    limit: int
    scanned_count: int
    settled_count: int
    canceled_count: int
    skipped_count: int
    error_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "runId": self.run_id,
            "runType": self.run_type,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "limit": self.limit,
            "scannedCount": self.scanned_count,
            "settledCount": self.settled_count,
            "canceledCount": self.canceled_count,
            "skippedCount": self.skipped_count,
            "errorCount": self.error_count,
        }


@dataclass(frozen=True, slots=True)
class CommissionWithdrawalReconcileItem:
    withdrawal_id: str
    out_bill_no: str
    previous_status: str
    current_status: str | None
    provider_state: str | None
    action: str
    error: str | None


@dataclass(frozen=True, slots=True)
class CommissionWithdrawalReconcileSummary:
    run_id: str
    run_type: str
    provider: str
    min_age_minutes: int
    limit: int
    started_at: str
    finished_at: str
    scanned_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int
    needs_attention_count: int
    error_count: int
    items: tuple[CommissionWithdrawalReconcileItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "runId": self.run_id,
            "runType": self.run_type,
            "provider": self.provider,
            "minAgeMinutes": self.min_age_minutes,
            "limit": self.limit,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "scannedCount": self.scanned_count,
            "succeededCount": self.succeeded_count,
            "failedCount": self.failed_count,
            "pendingCount": self.pending_count,
            "needsAttentionCount": self.needs_attention_count,
            "errorCount": self.error_count,
            "items": [asdict(item) for item in self.items],
        }


def current_membership_pending_payment_reconcile_config() -> MembershipPendingPaymentReconcileConfig:
    return MembershipPendingPaymentReconcileConfig(
        min_age_minutes=_env_int("PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_MIN_AGE_MINUTES", 5, minimum=0, maximum=24 * 60),
        limit=_env_int("PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_LIMIT", 100, minimum=1, maximum=500),
    )


def settle_due_membership_commissions(
    membership_commission_store: MembershipCommissionStore,
    *,
    limit: int,
    now: datetime | None = None,
) -> CommissionSettlementMaintenanceSummary:
    result = membership_commission_store.settle_due_commissions(now=now, limit=limit)
    return CommissionSettlementMaintenanceSummary(
        run_id=result.run_id,
        run_type="commission_settlement",
        started_at=result.started_at,
        finished_at=result.finished_at,
        limit=max(1, int(limit)),
        scanned_count=result.scanned_count,
        settled_count=result.settled_count,
        canceled_count=result.canceled_count,
        skipped_count=result.skipped_count,
        error_count=result.error_count,
    )


def reconcile_commission_withdrawals(
    membership_commission_store: MembershipCommissionStore,
    membership_payment_service: MembershipPaymentService,
    *,
    min_age_minutes: int,
    limit: int,
    now: datetime | None = None,
) -> CommissionWithdrawalReconcileSummary:
    started = now or _utc_now()
    run_id = f"run_{started.strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
    candidates = membership_commission_store.list_withdrawals_for_reconciliation(
        min_age_minutes=min_age_minutes,
        limit=limit,
        now=started,
    )
    items: list[CommissionWithdrawalReconcileItem] = []
    succeeded_count = 0
    failed_count = 0
    pending_count = 0
    needs_attention_count = 0
    error_count = 0
    for withdrawal in candidates:
        try:
            remote = membership_payment_service.query_commission_payout(withdrawal.out_bill_no, withdrawal_id=withdrawal.withdrawal_id)
            if remote.remote_status in {WITHDRAWAL_STATUS_SUCCEEDED, WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED, WITHDRAWAL_STATUS_NEEDS_ATTENTION}:
                updated = membership_commission_store.apply_withdrawal_provider_result(
                    out_bill_no=withdrawal.out_bill_no,
                    provider_state=remote.provider_state,
                    mapped_status=remote.remote_status,
                    transfer_bill_no=remote.provider_transfer_no,
                    amount_cent=remote.amount_cent,
                    appid=remote.appid,
                    raw_payload_json=remote.raw_payload_json,
                    provider_event_id=remote.provider_transfer_no or withdrawal.out_bill_no,
                    event_type="query",
                    failure_reason=remote.failure_reason,
                    signature_verified=True,
                )
                action = f"marked_{updated.status}"
                if updated.status == WITHDRAWAL_STATUS_SUCCEEDED:
                    succeeded_count += 1
                elif updated.status in {WITHDRAWAL_STATUS_FAILED, WITHDRAWAL_STATUS_CANCELED}:
                    failed_count += 1
                elif updated.status == WITHDRAWAL_STATUS_NEEDS_ATTENTION:
                    needs_attention_count += 1
                items.append(
                    CommissionWithdrawalReconcileItem(
                        withdrawal_id=withdrawal.withdrawal_id,
                        out_bill_no=withdrawal.out_bill_no,
                        previous_status=withdrawal.status,
                        current_status=updated.status,
                        provider_state=remote.provider_state,
                        action=action,
                        error=None,
                    )
                )
            else:
                pending_count += 1
                items.append(
                    CommissionWithdrawalReconcileItem(
                        withdrawal_id=withdrawal.withdrawal_id,
                        out_bill_no=withdrawal.out_bill_no,
                        previous_status=withdrawal.status,
                        current_status=withdrawal.status,
                        provider_state=remote.provider_state,
                        action=f"kept_{remote.remote_status}",
                        error=None,
                    )
                )
        except Exception as exc:
            error_count += 1
            items.append(
                CommissionWithdrawalReconcileItem(
                    withdrawal_id=withdrawal.withdrawal_id,
                    out_bill_no=withdrawal.out_bill_no,
                    previous_status=withdrawal.status,
                    current_status=None,
                    provider_state=None,
                    action="error",
                    error=str(exc),
                )
            )
    finished = _utc_now()
    summary = CommissionWithdrawalReconcileSummary(
        run_id=run_id,
        run_type="withdrawal_reconciliation",
        provider="wechat_pay",
        min_age_minutes=max(0, int(min_age_minutes)),
        limit=max(1, int(limit)),
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        scanned_count=len(candidates),
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        pending_count=pending_count,
        needs_attention_count=needs_attention_count,
        error_count=error_count,
        items=tuple(items),
    )
    membership_commission_store.record_reconciliation_run(
        run_id=run_id,
        run_type="withdrawal_reconciliation",
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        limit=summary.limit,
        scanned_count=summary.scanned_count,
        succeeded_count=summary.succeeded_count,
        failed_count=summary.failed_count,
        needs_attention_count=summary.needs_attention_count,
        error_count=summary.error_count,
        summary_json=json_dumps(summary.to_dict()),
    )
    return summary


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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
