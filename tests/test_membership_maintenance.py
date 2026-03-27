from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.system.membership_maintenance import reconcile_pending_wechat_membership_payments
from backend.system.membership_payment_service import MembershipRemotePaymentStatus, MembershipPaymentService
from backend.system.membership_store import MembershipStore


@pytest.fixture()
def membership_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_MANUAL_TEST_PAYMENT", "true")
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    yield


def _enable_wechat_native(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_key_path = tmp_path / "wechat-apiclient-key.pem"
    public_key_path = tmp_path / "wechatpay-public.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setenv("PLM_WECHAT_PAY_APP_ID", "wx-test-app")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.setenv("PLM_WECHAT_PAY_CERT_SERIAL_NO", "SERIALNO1234567890")
    monkeypatch.setenv("PLM_WECHAT_PAY_API_V3_KEY", "0123456789ABCDEF0123456789ABCDEF")
    monkeypatch.setenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", str(private_key_path))
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", str(public_key_path))
    monkeypatch.setenv("PLM_WECHAT_PAY_NOTIFY_URL", "https://learningpyramid.test/api/payments/wechat/notify")


def test_reconcile_pending_wechat_membership_payments_confirms_and_closes(
    membership_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    store = MembershipStore()
    payment_service = MembershipPaymentService()

    paid_order = store.create_order("user_paid", provider="wechat_native").order
    closed_order = store.create_order("user_closed", provider="wechat_native").order
    manual_order = store.create_order("user_manual", provider="manual_test").order

    def fake_query_payment_status(order) -> MembershipRemotePaymentStatus:
        if order.order_id == paid_order.order_id:
            return MembershipRemotePaymentStatus(
                provider="wechat_native",
                order_id=order.order_id,
                provider_trade_no="4200000000000000000100",
                remote_status="paid",
                paid_at="2026-03-26T10:00:00+08:00",
                amount_cent=1490,
                payer_id="wx-openid-paid",
                raw_payload_json='{"trade_state":"SUCCESS"}',
            )
        if order.order_id == closed_order.order_id:
            return MembershipRemotePaymentStatus(
                provider="wechat_native",
                order_id=order.order_id,
                provider_trade_no="4200000000000000000101",
                remote_status="closed",
                paid_at=None,
                amount_cent=None,
                payer_id=None,
                raw_payload_json='{"trade_state":"CLOSED"}',
            )
        raise AssertionError(f"unexpected order {order.order_id}")

    monkeypatch.setattr(payment_service, "query_payment_status", fake_query_payment_status)

    summary = reconcile_pending_wechat_membership_payments(
        store,
        payment_service,
        min_age_minutes=0,
        limit=10,
    )

    assert summary.scanned_count == 2
    assert summary.confirmed_count == 1
    assert summary.closed_count == 1
    assert summary.pending_count == 0
    assert summary.error_count == 0

    refreshed_paid = store.get_order(paid_order.order_id)
    refreshed_closed = store.get_order(closed_order.order_id)
    refreshed_manual = store.get_order(manual_order.order_id)

    assert refreshed_paid.status == "paid"
    assert refreshed_paid.provider_trade_no == "4200000000000000000100"
    assert refreshed_closed.status == "closed"
    assert refreshed_closed.remark == "remote payment state: closed"
    assert refreshed_manual.status == "pending"

    actions = {item.order_id: item.action for item in summary.items}
    assert actions[paid_order.order_id] == "confirmed_paid"
    assert actions[closed_order.order_id] == "closed_closed"


def test_reconcile_pending_wechat_membership_payments_records_item_errors(
    membership_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    store = MembershipStore()
    payment_service = MembershipPaymentService()
    order = store.create_order("user_error", provider="wechat_native").order

    monkeypatch.setattr(payment_service, "query_payment_status", lambda _order: (_ for _ in ()).throw(RuntimeError("network timeout")))

    summary = reconcile_pending_wechat_membership_payments(
        store,
        payment_service,
        min_age_minutes=0,
        limit=10,
    )

    assert summary.scanned_count == 1
    assert summary.error_count == 1
    assert summary.items[0].order_id == order.order_id
    assert summary.items[0].action == "error"
    assert "network timeout" in str(summary.items[0].error)
    assert store.get_order(order.order_id).status == "pending"
