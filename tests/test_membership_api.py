from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
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
        "baseMonthlyPriceCent": 1990,
        "firstOrderPriceCent": 1490,
        "renewalPriceCent": 1990,
        "currentPriceCent": 1490,
        "supportedPaymentProviders": ["manual_test"],
    }

    preview = client.post("/api/membership/orders/preview")
    assert preview.status_code == 200
    assert preview.json()["data"] == {
        "userId": user_id,
        "orderType": "first_purchase",
        "periodDays": 30,
        "listAmountCent": 1990,
        "firstOrderDiscountCent": 500,
        "couponDiscountCent": 0,
        "payableAmountCent": 1490,
        "couponId": None,
    }

    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    created_data = created.json()["data"]
    order_id = created_data["order"]["orderId"]
    assert created_data["order"]["status"] == "pending"
    assert created_data["order"]["orderType"] == "first_purchase"
    assert created_data["order"]["payableAmountCent"] == 1490
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
    assert confirmed_data["membership"]["currentPriceCent"] == 1990

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
    assert renewal_preview.json()["data"]["payableAmountCent"] == 1990


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


def test_invite_reward_coupon_flow(auth_env: None) -> None:
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

    invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert invitee_order.status_code == 200
    invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]

    invitee_confirm = invitee_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
    )
    assert invitee_confirm.status_code == 200

    inviter_invite_summary = inviter_client.get("/api/invites/me")
    assert inviter_invite_summary.status_code == 200
    assert inviter_invite_summary.json()["data"]["totalInvitedUsers"] == 1
    assert inviter_invite_summary.json()["data"]["rewardedInviteCount"] == 1
    assert inviter_invite_summary.json()["data"]["availableCouponCount"] == 1
    assert len(inviter_invite_summary.json()["data"]["recentInvites"]) == 1
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["inviteePublicUid"] == invitee_register.json()["data"]["publicUid"]
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["status"] == "rewarded"

    inviter_coupons = inviter_client.get("/api/coupons/me")
    assert inviter_coupons.status_code == 200
    coupons = inviter_coupons.json()["data"]
    assert len(coupons) == 1
    coupon_id = coupons[0]["couponId"]
    assert coupons[0]["amountCent"] == 500
    assert coupons[0]["status"] == "available"
    assert coupons[0]["source"] == "invite_reward"

    inviter_preview = inviter_client.post("/api/membership/orders/preview", json={"couponId": coupon_id})
    assert inviter_preview.status_code == 200
    assert inviter_preview.json()["data"]["couponDiscountCent"] == 500
    assert inviter_preview.json()["data"]["payableAmountCent"] == 990
    assert inviter_preview.json()["data"]["couponId"] == coupon_id

    inviter_order = inviter_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": coupon_id})
    assert inviter_order.status_code == 200
    inviter_order_data = inviter_order.json()["data"]["order"]
    inviter_order_id = inviter_order_data["orderId"]
    assert inviter_order_data["couponId"] == coupon_id
    assert inviter_order_data["couponDiscountCent"] == 500
    assert inviter_order_data["payableAmountCent"] == 990

    inviter_confirm = inviter_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": inviter_order_id, "providerTradeNo": f"manual_{inviter_order_id}"},
    )
    assert inviter_confirm.status_code == 200
    assert inviter_confirm.json()["data"]["order"]["status"] == "paid"

    inviter_coupons_after = inviter_client.get("/api/coupons/me")
    assert inviter_coupons_after.status_code == 200
    assert inviter_coupons_after.json()["data"][0]["status"] == "used"
    assert inviter_coupons_after.json()["data"][0]["usedOrderId"] == inviter_order_id


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


def test_admin_refund_rolls_back_unused_invite_reward(auth_env: None) -> None:
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

    inviter_coupons_before = inviter_client.get("/api/coupons/me")
    assert inviter_coupons_before.status_code == 200
    reward_coupon_id = inviter_coupons_before.json()["data"][0]["couponId"]
    assert inviter_coupons_before.json()["data"][0]["status"] == "available"

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{invitee_order_id}/refund",
        json={"reason": "chargeback"},
    )
    assert refunded.status_code == 200
    refunded_payload = refunded.json()["data"]
    assert refunded_payload["order"]["status"] == "refunded"
    assert refunded_payload["revokedRewardCouponId"] == reward_coupon_id

    invitee_summary = invitee_client.get("/api/membership/me")
    assert invitee_summary.status_code == 200
    assert invitee_summary.json()["data"]["currentStatus"] == "never_purchased"
    assert invitee_summary.json()["data"]["isActive"] is False
    assert invitee_summary.json()["data"]["isFirstOrderEligible"] is True

    inviter_invite_summary = inviter_client.get("/api/invites/me")
    assert inviter_invite_summary.status_code == 200
    assert inviter_invite_summary.json()["data"]["rewardedInviteCount"] == 0
    assert inviter_invite_summary.json()["data"]["availableCouponCount"] == 0
    assert inviter_invite_summary.json()["data"]["recentInvites"][0]["status"] == "bound"

    inviter_coupons_after = inviter_client.get("/api/coupons/me")
    assert inviter_coupons_after.status_code == 200
    assert inviter_coupons_after.json()["data"][0]["couponId"] == reward_coupon_id
    assert inviter_coupons_after.json()["data"][0]["status"] == "revoked"


def test_admin_refund_is_blocked_when_reward_coupon_has_already_been_used(auth_env: None) -> None:
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

    inviter_coupons = inviter_client.get("/api/coupons/me")
    assert inviter_coupons.status_code == 200
    reward_coupon_id = inviter_coupons.json()["data"][0]["couponId"]

    inviter_order = inviter_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": reward_coupon_id})
    assert inviter_order.status_code == 200
    inviter_order_id = inviter_order.json()["data"]["order"]["orderId"]
    inviter_confirm = inviter_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": inviter_order_id, "providerTradeNo": f"manual_{inviter_order_id}"},
    )
    assert inviter_confirm.status_code == 200

    refund_attempt = admin_client.post(
        f"/api/admin/membership/orders/{invitee_order_id}/refund",
        json={"reason": "chargeback"},
    )
    assert refund_attempt.status_code == 400
    assert refund_attempt.json()["error"]["code"] == "PRECONDITION"
    assert "invite reward coupon has already been used" in refund_attempt.json()["error"]["message"]


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
                "success_time": "2026-03-26T12:00:00+08:00",
                "amount": {"total": 1490},
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
            paid_at="2026-03-26T12:30:00+08:00",
            amount_cent=1490,
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
                "success_time": "2026-03-26T13:00:00+08:00",
                "amount": {"total": 1490},
                "payer": {"openid": "wx-openid-010"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            assert body is not None
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000001",
                "status": "PROCESSING",
                "amount": {"refund": 1490},
            }
        if method == "GET" and "/v3/refund/domestic/refunds/" in uri:
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000001",
                "status": "SUCCESS",
                "success_time": "2026-03-26T13:05:00+08:00",
                "amount": {"refund": 1490},
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
                "success_time": "2026-03-26T14:00:00+08:00",
                "amount": {"total": 1490},
                "payer": {"openid": "wx-openid-020"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            return {
                "out_trade_no": created_order_id,
                "out_refund_no": f"mrefund_{created_order_id}",
                "refund_id": "5000000000000000000002",
                "status": "PROCESSING",
                "amount": {"refund": 1490},
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
            refunded_at="2026-03-26T14:05:00+08:00",
            refund_amount_cent=1490,
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
