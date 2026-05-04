from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_commission_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.main import create_app
from backend.system.membership_payment_service import MembershipRemotePaymentStatus, MembershipRemoteRefundStatus


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv(
        "PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS",
        "admin@example.com,member@example.com,inviter@example.com,invitee@example.com",
    )
    monkeypatch.setenv("PLM_ENABLE_MANUAL_TEST_PAYMENT", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()
    yield
    _reset_caches()


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


def _activate_manual_membership(client: TestClient) -> str:
    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = str(created.json()["data"]["order"]["orderId"])
    confirmed = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["membership"]["isActive"] is True
    return order_id


def _create_settled_invited_membership(
    app,
    admin_client: TestClient,
    inviter_public_uid: str,
    *,
    invitee_email: str,
    paid_at: datetime,
) -> TestClient:
    invitee_client = TestClient(app)
    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": invitee_email, "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200
    with patch("backend.system.membership_store._utc_now", return_value=paid_at):
        created = invitee_client.post("/api/membership/orders", json={"provider": "manual_test"})
        assert created.status_code == 200
        order_id = created.json()["data"]["order"]["orderId"]
        confirmed = invitee_client.post(
            "/api/payments/membership/callback/manual_test",
            json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
        )
    assert confirmed.status_code == 200
    with patch("backend.system.membership_commission_store._utc_now", return_value=paid_at + timedelta(hours=24, seconds=1)):
        settled = admin_client.post("/api/admin/membership/commissions/settle")
    assert settled.status_code == 200
    assert settled.json()["data"]["settledCount"] == 1
    return invitee_client


def test_membership_purchase_immediately_enables_protected_llm_access(auth_env: None) -> None:
    client = TestClient(create_app())
    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    blocked = client.get("/api/profile/me/llm-settings")
    assert blocked.status_code == 400
    assert blocked.json()["error"]["message"] == "This feature requires active membership."

    _activate_manual_membership(client)

    allowed = client.get("/api/profile/me/llm-settings")
    assert allowed.status_code == 200
    assert allowed.json()["data"]["llmSource"] in {"none", "user", "global"}


def test_membership_refund_immediately_blocks_protected_llm_access(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    order_id = _activate_manual_membership(member_client)
    allowed = member_client.get("/api/profile/me/llm-settings")
    assert allowed.status_code == 200

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{order_id}/refund",
        json={"reason": "membership access regression test"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["data"]["order"]["status"] == "refunded"

    blocked = member_client.get("/api/profile/me/llm-settings")
    assert blocked.status_code == 400
    assert blocked.json()["error"]["message"] == "This feature requires active membership."


def test_membership_expiration_blocks_next_protected_llm_access(auth_env: None) -> None:
    client = TestClient(create_app())
    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    _activate_manual_membership(client)
    allowed = client.get("/api/profile/me/llm-settings")
    assert allowed.status_code == 200

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        blocked = client.get("/api/profile/me/llm-settings")

    assert blocked.status_code == 400
    assert blocked.json()["error"]["message"] == "This feature requires active membership."


def test_admin_can_grant_membership_months_without_creating_order(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_public_uid = member_register.json()["data"]["publicUid"]

    granted = admin_client.post(
        "/api/admin/membership/grants",
        json={"userId": member_public_uid, "months": 1},
    )
    assert granted.status_code == 200
    granted_data = granted.json()["data"]
    assert granted_data["months"] == 1
    assert granted_data["grantedDays"] == 30
    assert granted_data["membership"]["currentStatus"] == "active"
    assert granted_data["membership"]["isActive"] is True
    assert str(granted_data["entitlementId"]).startswith("ment_")
    assert str(granted_data["sourceRefId"]).startswith("admin_grant_")

    membership = member_client.get("/api/membership/me")
    assert membership.status_code == 200
    assert membership.json()["data"]["currentStatus"] == "active"

    orders = member_client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"] == []

    activity = admin_client.get("/api/admin/audit-logs")
    assert activity.status_code == 200
    assert activity.json()["data"][0]["actionType"] == "membership.months_granted"
    assert activity.json()["data"][0]["targetKind"] == "membership_entitlement"


def test_admin_membership_grant_extends_existing_active_membership(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_public_uid = member_register.json()["data"]["publicUid"]

    _activate_manual_membership(member_client)
    before = member_client.get("/api/membership/me")
    assert before.status_code == 200
    before_end = datetime.fromisoformat(before.json()["data"]["currentEndsAt"])

    granted = admin_client.post(
        "/api/admin/membership/grants",
        json={"userId": member_public_uid, "months": 2},
    )
    assert granted.status_code == 200
    granted_data = granted.json()["data"]
    assert granted_data["months"] == 2
    assert granted_data["grantedDays"] == 60
    assert granted_data["startAt"] == before_end.isoformat()

    after = member_client.get("/api/membership/me")
    assert after.status_code == 200
    after_end = datetime.fromisoformat(after.json()["data"]["currentEndsAt"])
    assert (after_end - before_end).total_seconds() == 60 * 24 * 3600


def test_membership_round_one_flow(auth_env: None) -> None:
    client = TestClient(create_app())

    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200
    user_id = register.json()["data"]["userId"]

    membership = client.get("/api/membership/me")
    assert membership.status_code == 200
    assert membership.json()["data"] == {
        "userId": user_id,
        "currentStatus": "never_purchased",
        "currentStartsAt": None,
        "currentEndsAt": None,
        "isActive": False,
        "isFirstOrderEligible": True,
            "baseMonthlyPriceCent": 2000,
            "firstOrderPriceCent": 2000,
            "renewalPriceCent": 2000,
            "currentPriceCent": 2000,
        "supportedPaymentProviders": ["manual_test"],
    }

    preview = client.post("/api/membership/orders/preview")
    assert preview.status_code == 200
    assert preview.json()["data"] == {
        "userId": user_id,
        "orderType": "first_purchase",
        "periodDays": 30,
        "listAmountCent": 2000,
        "firstOrderDiscountCent": 0,
        "couponDiscountCent": 0,
        "payableAmountCent": 2000,
        "couponId": None,
    }

    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    created_data = created.json()["data"]
    order_id = created_data["order"]["orderId"]
    assert created_data["order"]["status"] == "pending"
    assert created_data["order"]["orderType"] == "first_purchase"
    assert created_data["order"]["payableAmountCent"] == 2000
    assert created_data["paymentPayload"]["mode"] == "manual_test"
    assert created_data["paymentPayload"]["providerTradeNoHint"] == f"manual_{order_id}"
    assert created_data["reusedExistingOrder"] is False

    listed_orders = client.get("/api/membership/orders")
    assert listed_orders.status_code == 200
    assert len(listed_orders.json()["data"]) == 1
    assert listed_orders.json()["data"][0]["orderId"] == order_id
    assert listed_orders.json()["data"][0]["status"] == "pending"

    confirmed = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed.status_code == 200
    confirmed_data = confirmed.json()["data"]
    assert confirmed_data["paymentId"].startswith("mpay_")
    assert confirmed_data["idempotent"] is False
    assert confirmed_data["order"]["status"] == "paid"
    assert confirmed_data["order"]["paidAt"] is not None
    assert confirmed_data["order"]["entitlementId"].startswith("ment_")
    assert confirmed_data["membership"]["currentStatus"] == "active"
    assert confirmed_data["membership"]["isActive"] is True
    assert confirmed_data["membership"]["currentStartsAt"] is not None
    assert confirmed_data["membership"]["currentEndsAt"] is not None
    assert confirmed_data["membership"]["isFirstOrderEligible"] is False
    assert confirmed_data["membership"]["currentPriceCent"] == 2000

    confirmed_again = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed_again.status_code == 200
    assert confirmed_again.json()["data"]["idempotent"] is True
    assert confirmed_again.json()["data"]["order"]["status"] == "paid"

    renewal_preview = client.post("/api/membership/orders/preview")
    assert renewal_preview.status_code == 200
    assert renewal_preview.json()["data"]["orderType"] == "renewal"
    assert renewal_preview.json()["data"]["firstOrderDiscountCent"] == 0
    assert renewal_preview.json()["data"]["couponDiscountCent"] == 0
    assert renewal_preview.json()["data"]["payableAmountCent"] == 2000


def test_hosted_mode_disables_manual_test_payment_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv(
        "PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS",
        "admin@example.com,member@example.com,inviter@example.com,invitee@example.com",
    )
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()

    client = TestClient(create_app())
    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    membership = client.get("/api/membership/me")
    assert membership.status_code == 200
    assert membership.json()["data"]["supportedPaymentProviders"] == []

    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 400
    assert created.json()["error"]["code"] == "PRECONDITION"
    assert created.json()["error"]["message"] == "membership payments are unavailable in this deployment"

    confirmed = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": "mord_test", "providerTradeNo": "manual_mord_test"},
    )
    assert confirmed.status_code == 400
    assert confirmed.json()["error"]["code"] == "PRECONDITION"
    assert confirmed.json()["error"]["message"] == "membership payments are unavailable in this deployment"
    _reset_caches()


def test_create_membership_order_reuses_existing_pending_order(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    first = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert first.status_code == 200
    first_order_id = first.json()["data"]["order"]["orderId"]

    second = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["order"]["orderId"] == first_order_id
    assert second_data["reusedExistingOrder"] is True


def test_member_can_close_pending_membership_order(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})

    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    closed = client.post(f"/api/membership/orders/{order_id}/close")
    assert closed.status_code == 200
    closed_payload = closed.json()["data"]
    assert closed_payload["idempotent"] is False
    assert closed_payload["order"]["orderId"] == order_id
    assert closed_payload["order"]["status"] == "closed"
    assert closed_payload["order"]["closedAt"] is not None
    assert closed_payload["order"]["remark"] == "user closed pending membership order"
    assert closed_payload["membership"]["currentStatus"] == "never_purchased"

    closed_again = client.post(f"/api/membership/orders/{order_id}/close")
    assert closed_again.status_code == 200
    assert closed_again.json()["data"]["idempotent"] is True
    assert closed_again.json()["data"]["order"]["status"] == "closed"

    recreated = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert recreated.status_code == 200
    assert recreated.json()["data"]["order"]["orderId"] != order_id
    assert recreated.json()["data"]["reusedExistingOrder"] is False


def test_invite_binding_grants_invitee_discount_coupon_and_pending_commission(auth_env: None) -> None:
    app = create_app()
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_data = inviter_register.json()["data"]
    inviter_public_uid = inviter_data["publicUid"]

    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": "invitee@example.com", "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200

    invitee_summary = invitee_client.get("/api/invites/me")
    assert invitee_summary.status_code == 200
    assert invitee_summary.json()["data"]["boundInviteCode"] == inviter_public_uid
    assert invitee_summary.json()["data"]["availableCouponCount"] == 1

    invitee_coupons = invitee_client.get("/api/coupons/me")
    assert invitee_coupons.status_code == 200
    coupons = invitee_coupons.json()["data"]
    assert len(coupons) == 1
    coupon_id = coupons[0]["couponId"]
    assert coupons[0]["title"] == "邀请码 7.5 折券"
    assert coupons[0]["source"] == "invite_discount"
    assert coupons[0]["couponType"] == "percent"
    assert coupons[0]["discountRate"] == 75
    assert coupons[0]["amountCent"] == 0

    invitee_preview = invitee_client.post("/api/membership/orders/preview", json={"couponId": coupon_id})
    assert invitee_preview.status_code == 200
    assert invitee_preview.json()["data"]["listAmountCent"] == 2000
    assert invitee_preview.json()["data"]["firstOrderDiscountCent"] == 0
    assert invitee_preview.json()["data"]["couponDiscountCent"] == 500
    assert invitee_preview.json()["data"]["payableAmountCent"] == 1500
    assert invitee_preview.json()["data"]["couponId"] == coupon_id

    invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": coupon_id})
    assert invitee_order.status_code == 200
    invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]
    assert invitee_order.json()["data"]["order"]["listAmountCent"] == 2000
    assert invitee_order.json()["data"]["order"]["firstOrderDiscountCent"] == 0
    assert invitee_order.json()["data"]["order"]["couponDiscountCent"] == 500
    assert invitee_order.json()["data"]["order"]["payableAmountCent"] == 1500
    assert invitee_order.json()["data"]["order"]["couponId"] == coupon_id

    invitee_confirm = invitee_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
    )
    assert invitee_confirm.status_code == 200

    inviter_invite_summary = inviter_client.get("/api/invites/me")
    assert inviter_invite_summary.status_code == 200
    assert inviter_invite_summary.json()["data"]["totalInvitedUsers"] == 1
    assert inviter_invite_summary.json()["data"]["rewardedInviteCount"] == 0
    assert inviter_invite_summary.json()["data"]["availableCouponCount"] == 0
    assert inviter_invite_summary.json()["data"]["pendingCommissionCent"] == 500
    assert inviter_invite_summary.json()["data"]["withdrawableCommissionCent"] == 0
    assert len(inviter_invite_summary.json()["data"]["recentInvites"]) == 1
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["inviteePublicUid"] == invitee_register.json()["data"]["publicUid"]
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["status"] == "commission_pending"
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["discountCouponId"] == coupon_id
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["commissionAmountCent"] == 500

    inviter_coupons = inviter_client.get("/api/coupons/me")
    assert inviter_coupons.status_code == 200
    assert inviter_coupons.json()["data"] == []


def test_invite_commission_settles_once_after_refund_window(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": "invitee@example.com", "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200
    coupon_id = invitee_client.get("/api/coupons/me").json()["data"][0]["couponId"]

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2026-05-04T00:00:00+00:00")):
        invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": coupon_id})
        assert invitee_order.status_code == 200
        invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]
        invitee_confirm = invitee_client.post(
            "/api/payments/membership/callback/manual_test",
            json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
        )
    assert invitee_confirm.status_code == 200

    before = inviter_client.get("/api/commissions/me")
    assert before.status_code == 200
    assert before.json()["data"]["account"]["pendingCent"] == 500
    assert before.json()["data"]["account"]["withdrawableCent"] == 0

    early_settle = admin_client.post("/api/admin/membership/commissions/settle")
    assert early_settle.status_code == 200
    assert early_settle.json()["data"]["settledCount"] == 0

    with patch("backend.system.membership_commission_store._utc_now", return_value=datetime.fromisoformat("2026-05-05T00:00:01+00:00")):
        settled = admin_client.post("/api/admin/membership/commissions/settle")
    assert settled.status_code == 200
    assert settled.json()["data"]["settledCount"] == 1

    after = inviter_client.get("/api/commissions/me")
    assert after.status_code == 200
    assert after.json()["data"]["account"]["pendingCent"] == 0
    assert after.json()["data"]["account"]["withdrawableCent"] == 500
    assert after.json()["data"]["recentCommissions"][0]["status"] == "settled"

    with patch("backend.system.membership_commission_store._utc_now", return_value=datetime.fromisoformat("2026-05-05T00:00:02+00:00")):
        settled_again = admin_client.post("/api/admin/membership/commissions/settle")
    assert settled_again.status_code == 200
    assert settled_again.json()["data"]["settledCount"] == 0


def test_commission_withdrawal_request_reserves_balance_and_lists_history(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    _create_settled_invited_membership(
        app,
        admin_client,
        inviter_public_uid,
        invitee_email="invitee@example.com",
        paid_at=datetime.fromisoformat("2026-05-04T00:00:00+00:00"),
    )

    before = inviter_client.get("/api/commissions/me")
    assert before.status_code == 200
    assert before.json()["data"]["account"]["withdrawableCent"] == 500
    assert before.json()["data"]["account"]["reservedCent"] == 0

    requested = inviter_client.post(
        "/api/commissions/withdrawals",
        json={"amountCent": 500, "wechatOpenId": "openid_inviter_001"},
    )
    assert requested.status_code == 200
    withdrawal = requested.json()["data"]
    assert withdrawal["withdrawalId"].startswith("mwd_")
    assert withdrawal["amountCent"] == 500
    assert withdrawal["targetType"] == "wechat_pay"
    assert withdrawal["wechatOpenIdMasked"].startswith("openid_")
    assert withdrawal["status"] == "processing"
    assert withdrawal["providerTransferNo"].startswith("manual_")

    after = inviter_client.get("/api/commissions/me")
    assert after.status_code == 200
    assert after.json()["data"]["account"]["withdrawableCent"] == 0
    assert after.json()["data"]["account"]["reservedCent"] == 500
    assert after.json()["data"]["account"]["paidOutCent"] == 0

    history = inviter_client.get("/api/commissions/withdrawals")
    assert history.status_code == 200
    assert len(history.json()["data"]) == 1
    assert history.json()["data"][0]["withdrawalId"] == withdrawal["withdrawalId"]
    assert history.json()["data"][0]["status"] == "processing"


def test_commission_withdrawal_rejects_insufficient_balance_and_missing_wechat_identity(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    empty_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]
    empty_register = empty_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert empty_register.status_code == 200

    insufficient = empty_client.post(
        "/api/commissions/withdrawals",
        json={"amountCent": 500, "wechatOpenId": "openid_empty"},
    )
    assert insufficient.status_code == 400
    assert insufficient.json()["error"]["code"] == "PRECONDITION"
    assert insufficient.json()["error"]["message"] == "withdrawal amount exceeds withdrawable commission balance"

    _create_settled_invited_membership(
        app,
        admin_client,
        inviter_public_uid,
        invitee_email="invitee@example.com",
        paid_at=datetime.fromisoformat("2026-05-04T00:00:00+00:00"),
    )

    missing_identity = inviter_client.post("/api/commissions/withdrawals", json={"amountCent": 500})
    assert missing_identity.status_code == 400
    assert missing_identity.json()["error"]["code"] == "PRECONDITION"
    assert missing_identity.json()["error"]["message"] == "wechat receiving identity is required"


def test_commission_withdrawal_provider_results_are_idempotent(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    _create_settled_invited_membership(
        app,
        admin_client,
        inviter_public_uid,
        invitee_email="invitee-one@example.com",
        paid_at=datetime.fromisoformat("2026-05-04T00:00:00+00:00"),
    )
    first = inviter_client.post(
        "/api/commissions/withdrawals",
        json={"amountCent": 500, "wechatOpenId": "openid_inviter_001"},
    )
    assert first.status_code == 200
    first_withdrawal_id = first.json()["data"]["withdrawalId"]

    succeeded = admin_client.post(
        f"/api/admin/membership/withdrawals/{first_withdrawal_id}/resolve",
        json={"status": "succeeded", "providerTransferNo": "transfer_success_001"},
    )
    assert succeeded.status_code == 200
    assert succeeded.json()["data"]["status"] == "succeeded"
    succeeded_again = admin_client.post(
        f"/api/admin/membership/withdrawals/{first_withdrawal_id}/resolve",
        json={"status": "succeeded", "providerTransferNo": "transfer_success_001"},
    )
    assert succeeded_again.status_code == 200
    assert succeeded_again.json()["data"]["status"] == "succeeded"

    after_success = inviter_client.get("/api/commissions/me")
    assert after_success.status_code == 200
    assert after_success.json()["data"]["account"]["reservedCent"] == 0
    assert after_success.json()["data"]["account"]["withdrawableCent"] == 0
    assert after_success.json()["data"]["account"]["paidOutCent"] == 500

    _create_settled_invited_membership(
        app,
        admin_client,
        inviter_public_uid,
        invitee_email="invitee-two@example.com",
        paid_at=datetime.fromisoformat("2026-05-06T00:00:00+00:00"),
    )
    second = inviter_client.post(
        "/api/commissions/withdrawals",
        json={"amountCent": 500, "wechatOpenId": "openid_inviter_001"},
    )
    assert second.status_code == 200
    second_withdrawal_id = second.json()["data"]["withdrawalId"]

    failed = admin_client.post(
        f"/api/admin/membership/withdrawals/{second_withdrawal_id}/resolve",
        json={"status": "failed", "providerTransferNo": "transfer_failed_001", "failureReason": "provider rejected"},
    )
    assert failed.status_code == 200
    assert failed.json()["data"]["status"] == "failed"
    assert failed.json()["data"]["failureReason"] == "provider rejected"
    failed_again = admin_client.post(
        f"/api/admin/membership/withdrawals/{second_withdrawal_id}/resolve",
        json={"status": "failed", "providerTransferNo": "transfer_failed_001", "failureReason": "provider rejected"},
    )
    assert failed_again.status_code == 200
    assert failed_again.json()["data"]["status"] == "failed"

    after_failure = inviter_client.get("/api/commissions/me")
    assert after_failure.status_code == 200
    assert after_failure.json()["data"]["account"]["reservedCent"] == 0
    assert after_failure.json()["data"]["account"]["withdrawableCent"] == 500
    assert after_failure.json()["data"]["account"]["paidOutCent"] == 500


def test_invite_code_cannot_be_bound_after_first_paid_order(auth_env: None) -> None:
    app = create_app()
    inviter_client = TestClient(app)
    member_client = TestClient(app)

    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    order = member_client.post("/api/membership/orders", json={"provider": "manual_test"})
    order_id = order.json()["data"]["order"]["orderId"]
    confirm = member_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirm.status_code == 200

    bind = member_client.post("/api/invites/bind", json={"inviteCode": inviter_public_uid})
    assert bind.status_code == 400
    assert bind.json()["error"]["code"] == "PRECONDITION"


def test_admin_refund_recomputes_membership_chain_and_restores_coupon(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_public_uid = member_register.json()["data"]["publicUid"]

    granted_coupon = admin_client.post(
        "/api/admin/membership/coupons/grant",
        json={
            "userId": member_public_uid,
            "amountCent": 500,
            "title": "后台补偿 5 元券",
            "expiresInDays": 30,
            "minSpendCent": 0,
        },
    )
    assert granted_coupon.status_code == 200
    coupon_id = granted_coupon.json()["data"]["couponId"]

    first_order = member_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": coupon_id})
    assert first_order.status_code == 200
    first_order_id = first_order.json()["data"]["order"]["orderId"]
    first_confirm = member_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": first_order_id, "providerTradeNo": f"manual_{first_order_id}"},
    )
    assert first_confirm.status_code == 200

    renewal_order = member_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert renewal_order.status_code == 200
    renewal_order_id = renewal_order.json()["data"]["order"]["orderId"]
    renewal_confirm = member_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": renewal_order_id, "providerTradeNo": f"manual_{renewal_order_id}"},
    )
    assert renewal_confirm.status_code == 200

    summary_before_refund = member_client.get("/api/membership/me")
    assert summary_before_refund.status_code == 200
    end_before_refund = datetime.fromisoformat(summary_before_refund.json()["data"]["currentEndsAt"])

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{first_order_id}/refund",
        json={"reason": "manual rollback"},
    )
    assert refunded.status_code == 200
    refunded_payload = refunded.json()["data"]
    assert refunded_payload["order"]["status"] == "refunded"
    assert refunded_payload["restoredCouponId"] == coupon_id
    assert refunded_payload["restoredCouponStatus"] == "available"
    assert refunded_payload["revokedRewardCouponId"] is None
    assert refunded_payload["idempotent"] is False

    refunded_again = admin_client.post(
        f"/api/admin/membership/orders/{first_order_id}/refund",
        json={"reason": "manual rollback"},
    )
    assert refunded_again.status_code == 200
    assert refunded_again.json()["data"]["idempotent"] is True
    assert refunded_again.json()["data"]["order"]["status"] == "refunded"

    summary_after_refund = member_client.get("/api/membership/me")
    assert summary_after_refund.status_code == 200
    summary_after_refund_data = summary_after_refund.json()["data"]
    assert summary_after_refund_data["currentStatus"] == "active"
    assert summary_after_refund_data["isActive"] is True
    end_after_refund = datetime.fromisoformat(summary_after_refund_data["currentEndsAt"])
    assert end_after_refund < end_before_refund
    assert (end_before_refund - end_after_refund).total_seconds() > 29 * 24 * 3600

    member_orders = member_client.get("/api/membership/orders")
    assert member_orders.status_code == 200
    status_by_order_id = {item["orderId"]: item["status"] for item in member_orders.json()["data"]}
    assert status_by_order_id[first_order_id] == "refunded"
    assert status_by_order_id[renewal_order_id] == "paid"

    member_coupons = member_client.get("/api/coupons/me")
    assert member_coupons.status_code == 200
    coupon_by_id = {item["couponId"]: item for item in member_coupons.json()["data"]}
    assert coupon_by_id[coupon_id]["status"] == "available"
    assert coupon_by_id[coupon_id]["usedOrderId"] is None
    assert coupon_by_id[coupon_id]["usedAt"] is None


def test_admin_refund_rejects_manual_order_after_24_hours(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    order_id = _activate_manual_membership(member_client)

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        refund_attempt = admin_client.post(
            f"/api/admin/membership/orders/{order_id}/refund",
            json={"reason": "late manual refund"},
        )

    assert refund_attempt.status_code == 400
    assert refund_attempt.json()["error"]["code"] == "PRECONDITION"
    assert refund_attempt.json()["error"]["message"] == "Membership refund period has expired."

    orders = member_client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == order_id
    assert orders.json()["data"][0]["status"] == "paid"


def test_admin_refund_allows_manual_order_at_exact_24_hour_boundary(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    paid_at = datetime.fromisoformat("2026-05-04T00:00:00+00:00")

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    with patch("backend.system.membership_store._utc_now", return_value=paid_at):
        order_id = _activate_manual_membership(member_client)

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2026-05-05T00:00:00+00:00")):
        refund_attempt = admin_client.post(
            f"/api/admin/membership/orders/{order_id}/refund",
            json={"reason": "boundary refund"},
        )

    assert refund_attempt.status_code == 200
    assert refund_attempt.json()["data"]["order"]["status"] == "refunded"


def test_admin_refund_rejects_paid_order_without_successful_payment_time(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    order_id = _activate_manual_membership(member_client)
    membership_store = get_membership_store()
    conn = sqlite3.connect(str(membership_store.db_path))
    try:
        conn.execute("UPDATE membership_orders SET paid_at = NULL WHERE order_id = ?", (order_id,))
        conn.commit()
    finally:
        conn.close()

    refund_attempt = admin_client.post(
        f"/api/admin/membership/orders/{order_id}/refund",
        json={"reason": "missing paid_at"},
    )

    assert refund_attempt.status_code == 400
    assert refund_attempt.json()["error"]["code"] == "PRECONDITION"
    assert refund_attempt.json()["error"]["message"] == "membership order successful payment time is unavailable"


def test_admin_refund_cancels_pending_invite_commission(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": "invitee@example.com", "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200

    invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert invitee_order.status_code == 200
    invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]
    invitee_confirm = invitee_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
    )
    assert invitee_confirm.status_code == 200

    inviter_commissions_before = inviter_client.get("/api/commissions/me")
    assert inviter_commissions_before.status_code == 200
    assert inviter_commissions_before.json()["data"]["account"]["pendingCent"] == 500
    assert inviter_commissions_before.json()["data"]["account"]["withdrawableCent"] == 0
    assert inviter_commissions_before.json()["data"]["recentCommissions"][0]["sourceOrderId"] == invitee_order_id
    assert inviter_commissions_before.json()["data"]["recentCommissions"][0]["status"] == "pending"

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{invitee_order_id}/refund",
        json={"reason": "chargeback"},
    )
    assert refunded.status_code == 200
    refunded_payload = refunded.json()["data"]
    assert refunded_payload["order"]["status"] == "refunded"
    assert refunded_payload["revokedRewardCouponId"] is None

    invitee_summary = invitee_client.get("/api/membership/me")
    assert invitee_summary.status_code == 200
    assert invitee_summary.json()["data"]["currentStatus"] == "never_purchased"
    assert invitee_summary.json()["data"]["isActive"] is False
    assert invitee_summary.json()["data"]["isFirstOrderEligible"] is True

    inviter_invite_summary = inviter_client.get("/api/invites/me")
    assert inviter_invite_summary.status_code == 200
    assert inviter_invite_summary.json()["data"]["rewardedInviteCount"] == 0
    assert inviter_invite_summary.json()["data"]["availableCouponCount"] == 0
    assert inviter_invite_summary.json()["data"]["pendingCommissionCent"] == 0
    assert inviter_invite_summary.json()["data"]["withdrawableCommissionCent"] == 0
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["status"] == "bound"

    inviter_coupons_after = inviter_client.get("/api/coupons/me")
    assert inviter_coupons_after.status_code == 200
    assert inviter_coupons_after.json()["data"] == []

    inviter_commissions_after = inviter_client.get("/api/commissions/me")
    assert inviter_commissions_after.status_code == 200
    assert inviter_commissions_after.json()["data"]["account"]["pendingCent"] == 0
    assert inviter_commissions_after.json()["data"]["account"]["canceledCent"] == 500
    assert inviter_commissions_after.json()["data"]["recentCommissions"][0]["status"] == "canceled"
    assert inviter_commissions_after.json()["data"]["recentCommissions"][0]["cancelReason"] == "chargeback"


def test_canceled_invite_commission_does_not_settle_after_refund_window(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_public_uid = inviter_register.json()["data"]["publicUid"]

    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": "invitee@example.com", "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200

    invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert invitee_order.status_code == 200
    invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]
    invitee_confirm = invitee_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
    )
    assert invitee_confirm.status_code == 200

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{invitee_order_id}/refund",
        json={"reason": "chargeback"},
    )
    assert refunded.status_code == 200

    with patch("backend.system.membership_commission_store._utc_now", return_value=datetime.fromisoformat("2026-05-05T00:00:01+00:00")):
        settled = admin_client.post("/api/admin/membership/commissions/settle")
    assert settled.status_code == 200
    assert settled.json()["data"]["settledCount"] == 0

    inviter_commissions = inviter_client.get("/api/commissions/me")
    assert inviter_commissions.status_code == 200
    assert inviter_commissions.json()["data"]["account"]["pendingCent"] == 0
    assert inviter_commissions.json()["data"]["account"]["withdrawableCent"] == 0
    assert inviter_commissions.json()["data"]["account"]["canceledCent"] == 500
    assert inviter_commissions.json()["data"]["recentCommissions"][0]["status"] == "canceled"


def test_wechat_native_order_can_be_created_and_synced(auth_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            assert body is not None
            assert body["notify_url"] == "https://learningpyramid.test/api/payments/wechat/notify"
            assert len(str(body["out_trade_no"])) <= 32
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            assert len(order_id) <= 32
            return {
                "out_trade_no": order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000001",
                "success_time": "2026-05-04T12:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-001"},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    membership = client.get("/api/membership/me")
    assert membership.status_code == 200
    assert membership.json()["data"]["supportedPaymentProviders"] == ["manual_test", "wechat_native"]

    created = client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_data = created.json()["data"]
    order_id = created_data["order"]["orderId"]
    assert created_data["order"]["provider"] == "wechat_native"
    assert created_data["paymentPayload"]["mode"] == "wechat_native"
    assert created_data["paymentPayload"]["providerLabel"] == "微信扫码支付"
    assert created_data["paymentPayload"]["statusCheckSupported"] is True
    assert created_data["paymentPayload"]["codeUrl"] == "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"
    assert created_data["paymentPayload"]["qrImageDataUrl"].startswith("data:image/svg+xml;base64,")

    synced = client.post(f"/api/membership/orders/{order_id}/sync-payment")
    assert synced.status_code == 200
    synced_data = synced.json()["data"]
    assert synced_data["confirmed"] is True
    assert synced_data["order"]["status"] == "paid"
    assert synced_data["order"]["orderId"] == order_id
    assert synced_data["remote"]["remoteStatus"] == "paid"
    assert synced_data["remote"]["providerTradeNo"] == "4200000000000000000001"
    assert synced_data["membership"]["currentStatus"] == "active"


def test_user_membership_callback_rejects_wechat_native(auth_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    client = TestClient(create_app())
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    created = client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    confirmed = client.post(
        "/api/payments/membership/callback/wechat_native",
        json={"orderId": order_id, "providerTradeNo": "4200000000000000009999"},
    )
    assert confirmed.status_code == 400
    assert confirmed.json()["error"]["code"] == "PRECONDITION"
    assert confirmed.json()["error"]["message"] == "membership payment callback is only available for manual_test"

    membership = client.get("/api/membership/me")
    assert membership.status_code == 200
    assert membership.json()["data"]["currentStatus"] == "never_purchased"

    orders = client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == order_id
    assert orders.json()["data"][0]["status"] == "pending"


def test_wechat_closed_payment_sync_marks_order_closed(auth_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native-closed"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "CLOSED",
                "transaction_id": "4200000000000000000003",
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    register = client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    created = client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    synced = client.post(f"/api/membership/orders/{order_id}/sync-payment")
    assert synced.status_code == 200
    synced_payload = synced.json()["data"]
    assert synced_payload["confirmed"] is False
    assert synced_payload["idempotent"] is False
    assert synced_payload["order"]["status"] == "closed"
    assert synced_payload["order"]["closedAt"] is not None
    assert synced_payload["order"]["remark"] == "remote payment state: closed"
    assert synced_payload["remote"]["remoteStatus"] == "closed"
    assert synced_payload["paymentId"].startswith("mpay_")
    assert synced_payload["membership"]["currentStatus"] == "never_purchased"

    orders = client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == order_id
    assert orders.json()["data"][0]["status"] == "closed"


def test_wechat_notify_endpoint_is_public(auth_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    member_client = TestClient(app)
    notify_client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)
    monkeypatch.setattr(
        payment_service,
        "parse_payment_notification",
        lambda provider, headers, body_text: MembershipRemotePaymentStatus(
            provider="wechat_native",
            order_id=created_order_id,
            provider_trade_no="4200000000000000000002",
            remote_status="paid",
            paid_at="2026-05-04T12:30:00+08:00",
            amount_cent=2000,
            payer_id="wx-openid-002",
            raw_payload_json='{"event":"TRANSACTION.SUCCESS"}',
        ),
    )

    register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert register.status_code == 200

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_order_id = created.json()["data"]["order"]["orderId"]

    notify_response = notify_client.post("/api/payments/wechat/notify", content='{"id":"fake"}')
    assert notify_response.status_code == 200
    assert notify_response.text == "success"

    orders = member_client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == created_order_id
    assert orders.json()["data"][0]["status"] == "paid"


def test_admin_wechat_refund_flows_from_pending_to_refunded(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000010",
                "success_time": "2026-05-04T13:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-010"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            assert body is not None
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000001",
                "status": "PROCESSING",
                "amount": {"refund": 2000},
            }
        if method == "GET" and "/v3/refund/domestic/refunds/" in uri:
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000001",
                "status": "SUCCESS",
                "success_time": "2026-05-04T13:05:00+08:00",
                "amount": {"refund": 2000},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_order_id = created.json()["data"]["order"]["orderId"]

    synced_payment = member_client.post(f"/api/membership/orders/{created_order_id}/sync-payment")
    assert synced_payment.status_code == 200
    assert synced_payment.json()["data"]["order"]["status"] == "paid"

    requested_refund = admin_client.post(
        f"/api/admin/membership/orders/{created_order_id}/refund",
        json={"reason": "wechat refund request"},
    )
    assert requested_refund.status_code == 200
    requested_payload = requested_refund.json()["data"]
    assert requested_payload["order"]["status"] == "refund_pending"
    assert requested_payload["completed"] is False
    assert requested_payload["refundRequestSubmitted"] is True
    assert requested_payload["remoteStatus"] == "refund_pending"
    assert requested_payload["providerRefundNo"] == f"mrefund_{created_order_id}"

    membership_during_refund = member_client.get("/api/membership/me")
    assert membership_during_refund.status_code == 200
    assert membership_during_refund.json()["data"]["currentStatus"] == "active"

    synced_refund = admin_client.post(
        f"/api/admin/membership/orders/{created_order_id}/refund",
        json={"reason": "wechat refund request"},
    )
    assert synced_refund.status_code == 200
    synced_payload = synced_refund.json()["data"]
    assert synced_payload["order"]["status"] == "refunded"
    assert synced_payload["completed"] is True
    assert synced_payload["remoteStatus"] == "refunded"

    membership_after_refund = member_client.get("/api/membership/me")
    assert membership_after_refund.status_code == 200
    assert membership_after_refund.json()["data"]["currentStatus"] == "never_purchased"


def test_admin_wechat_refund_rejects_new_request_after_24_hours_without_calling_provider(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    payment_service = get_membership_payment_service()
    refund_requested = False

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        nonlocal refund_requested
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000011",
                "success_time": "2026-05-04T13:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-011"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            refund_requested = True
            raise AssertionError("refund provider request should not be called for late refund")
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_order_id = created.json()["data"]["order"]["orderId"]

    synced_payment = member_client.post(f"/api/membership/orders/{created_order_id}/sync-payment")
    assert synced_payment.status_code == 200
    assert synced_payment.json()["data"]["order"]["status"] == "paid"

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        requested_refund = admin_client.post(
            f"/api/admin/membership/orders/{created_order_id}/refund",
            json={"reason": "late wechat refund"},
        )

    assert requested_refund.status_code == 400
    assert requested_refund.json()["error"]["code"] == "PRECONDITION"
    assert requested_refund.json()["error"]["message"] == "Membership refund period has expired."
    assert refund_requested is False

    orders = member_client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == created_order_id
    assert orders.json()["data"][0]["status"] == "paid"


def test_refund_pending_wechat_order_can_finish_after_24_hour_window(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000012",
                "success_time": "2026-05-04T13:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-012"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            assert body is not None
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000003",
                "status": "PROCESSING",
                "amount": {"refund": 2000},
            }
        if method == "GET" and "/v3/refund/domestic/refunds/" in uri:
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000003",
                "status": "SUCCESS",
                "success_time": "2099-01-01T00:00:00+00:00",
                "amount": {"refund": 2000},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_order_id = created.json()["data"]["order"]["orderId"]

    synced_payment = member_client.post(f"/api/membership/orders/{created_order_id}/sync-payment")
    assert synced_payment.status_code == 200
    assert synced_payment.json()["data"]["order"]["status"] == "paid"

    requested_refund = admin_client.post(
        f"/api/admin/membership/orders/{created_order_id}/refund",
        json={"reason": "wechat refund request"},
    )
    assert requested_refund.status_code == 200
    assert requested_refund.json()["data"]["order"]["status"] == "refund_pending"

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        synced_refund = admin_client.post(
            f"/api/admin/membership/orders/{created_order_id}/refund",
            json={"reason": "wechat refund request"},
        )

    assert synced_refund.status_code == 200
    assert synced_refund.json()["data"]["order"]["status"] == "refunded"
    assert synced_refund.json()["data"]["remoteStatus"] == "refunded"


def test_wechat_refund_notify_endpoint_is_public(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    _reset_caches()
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)
    notify_client = TestClient(app)
    payment_service = get_membership_payment_service()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        if method == "POST" and uri == "/v3/pay/transactions/native":
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000020",
                "success_time": "2026-05-04T14:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-020"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000002",
                "status": "PROCESSING",
                "amount": {"refund": 2000},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)
    monkeypatch.setattr(
        payment_service,
        "parse_refund_notification",
        lambda provider, headers, body_text: MembershipRemoteRefundStatus(
            provider="wechat_native",
            order_id=created_order_id,
            refund_out_trade_no=f"mrefund_{created_order_id}",
            provider_refund_no="5000000000000000000002",
            remote_status="refunded",
            refunded_at="2026-05-04T14:05:00+08:00",
            refund_amount_cent=2000,
            raw_payload_json='{"event":"REFUND.SUCCESS"}',
        ),
    )

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    created_order_id = created.json()["data"]["order"]["orderId"]

    synced_payment = member_client.post(f"/api/membership/orders/{created_order_id}/sync-payment")
    assert synced_payment.status_code == 200

    requested_refund = admin_client.post(
        f"/api/admin/membership/orders/{created_order_id}/refund",
        json={"reason": "wechat refund request"},
    )
    assert requested_refund.status_code == 200
    assert requested_refund.json()["data"]["order"]["status"] == "refund_pending"

    notify_response = notify_client.post("/api/payments/wechat/refund-notify", content='{"id":"fake"}')
    assert notify_response.status_code == 200
    assert notify_response.text == "success"

    orders = member_client.get("/api/membership/orders")
    assert orders.status_code == 200
    assert orders.json()["data"][0]["orderId"] == created_order_id
    assert orders.json()["data"][0]["status"] == "refunded"
