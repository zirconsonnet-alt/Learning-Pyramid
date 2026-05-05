from __future__ import annotations

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
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "admin@example.com,inviter@example.com")
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


def _register_user(client: TestClient, email: str, *, invite_code: str | None = None) -> dict:
    payload: dict[str, str] = {"email": email, "password": "password123"}
    if invite_code:
        payload["inviteCode"] = invite_code
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200
    return response.json()["data"]


def _create_settled_invited_membership(
    app,
    admin_client: TestClient,
    inviter_public_uid: str,
    *,
    invitee_email: str,
    paid_at: datetime,
) -> TestClient:
    invitee_client = TestClient(app)
    _register_user(invitee_client, invitee_email, invite_code=inviter_public_uid)
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


def _bind_manual_payout_identity(client: TestClient, *, openid: str = "openid_inviter_001") -> dict:
    started = client.post(
        "/api/commissions/payout-identity/wechat/binding-attempts",
        json={"channel": "manual_test", "returnUrl": "http://testserver/membership"},
    )
    assert started.status_code == 200
    attempt = started.json()["data"]
    completed = client.post(
        "/api/commissions/payout-identity/wechat/bind",
        json={
            "bindingAttemptId": attempt["bindingAttemptId"],
            "authorizationCode": openid,
            "state": attempt["state"],
        },
    )
    assert completed.status_code == 200
    return completed.json()["data"]


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


def test_admin_can_manage_users_and_activity_logs(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")
    assert admin_register["roles"] == ["super_admin"]

    member_register = _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])
    member_user_id = member_register["userId"]

    granted = admin_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": True},
    )
    assert granted.status_code == 200
    assert "admin" in granted.json()["data"]["roles"]

    created_project = member_client.post("/api/projects", json={"title": "Member Study Project"})
    assert created_project.status_code == 200
    project_id = created_project.json()["data"]["projectId"]
    synced = member_client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-09",
            "dateTo": "2026-04-09",
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": "2026-04-09",
                    "effectiveMs": 36_000,
                    "watchMs": 12_000,
                    "composeMs": 8_000,
                    "reviewMs": 10_000,
                    "qaMs": 6_000,
                    "effectiveRanges": [{"startMs": 0, "endMs": 36_000}],
                    "watchRanges": [{"startMs": 0, "endMs": 12_000}],
                    "composeRanges": [{"startMs": 12_000, "endMs": 20_000}],
                    "reviewRanges": [{"startMs": 20_000, "endMs": 30_000}],
                    "qaRanges": [{"startMs": 30_000, "endMs": 36_000}],
                }
            ],
        },
    )
    assert synced.status_code == 200

    member_overview = member_client.get("/api/admin/overview")
    assert member_overview.status_code == 200

    forbidden_role_update = member_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": False},
    )
    assert forbidden_role_update.status_code == 403
    assert forbidden_role_update.json()["error"]["message"] == "Super administrator access required"

    overview = admin_client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["data"]["users"] == 2
    assert overview.json()["data"]["activeUsers"] == 2
    assert overview.json()["data"]["studyUsers"] == 1
    assert overview.json()["data"]["studyUsers7d"] == 1
    assert overview.json()["data"]["effectiveStudyMs"] == 36_000
    assert overview.json()["data"]["watchMs"] == 12_000
    assert overview.json()["data"]["composeMs"] == 8_000
    assert overview.json()["data"]["reviewMs"] == 10_000
    assert overview.json()["data"]["qaMs"] == 6_000

    users = admin_client.get("/api/admin/users")
    assert users.status_code == 200
    payload_by_id = {item["userId"]: item for item in users.json()["data"]}
    assert payload_by_id[member_user_id]["status"] == "active"

    user_detail = admin_client.get(f"/api/admin/users/{member_user_id}")
    assert user_detail.status_code == 200
    assert user_detail.json()["data"]["userId"] == member_user_id

    suspended = admin_client.patch(f"/api/admin/users/{member_user_id}/status", json={"status": "suspended"})
    assert suspended.status_code == 200
    assert suspended.json()["data"]["status"] == "suspended"

    activity = admin_client.get("/api/admin/activity")
    assert activity.status_code == 200
    action_types = [item["actionType"] for item in activity.json()["data"]]
    assert "user.role_updated" in action_types
    assert "user.status_updated" in action_types

    audit_logs = admin_client.get("/api/admin/audit-logs")
    assert audit_logs.status_code == 200
    assert [item["actionType"] for item in audit_logs.json()["data"]] == action_types


def test_non_admin_cannot_access_admin_endpoints(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    normal_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(normal_client, "normal@example.com", invite_code=admin_register["publicUid"])

    denied = normal_client.get("/api/admin/overview")
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "Administrator access required"


def test_admin_user_role_filter(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    role_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")
    admin_user_id = admin_register["userId"]

    role_register = _register_user(role_client, "role@example.com", invite_code=admin_register["publicUid"])
    role_user_id = role_register["userId"]

    member_register = _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])
    member_user_id = member_register["userId"]

    granted = admin_client.patch(f"/api/admin/users/{role_user_id}/roles", json={"role": "admin", "enabled": True})
    assert granted.status_code == 200

    admin_only = admin_client.get("/api/admin/users?role=admin")
    assert admin_only.status_code == 200
    assert [item["userId"] for item in admin_only.json()["data"]] == [role_user_id]

    super_admin_only = admin_client.get("/api/admin/users?role=super_admin")
    assert super_admin_only.status_code == 200
    assert [item["userId"] for item in super_admin_only.json()["data"]] == [admin_user_id]

    no_role = admin_client.get("/api/admin/users?role=none")
    assert no_role.status_code == 200
    assert [item["userId"] for item in no_role.json()["data"]] == [member_user_id]


def test_admin_can_manage_membership_operations(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")

    inviter_payload = _register_user(inviter_client, "inviter@example.com")
    inviter_public_uid = inviter_payload["publicUid"]

    invitee_payload = _register_user(invitee_client, "invitee@example.com", invite_code=inviter_public_uid)
    invitee_public_uid = invitee_payload["publicUid"]

    invitee_order = invitee_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert invitee_order.status_code == 200
    invitee_order_id = invitee_order.json()["data"]["order"]["orderId"]

    invitee_confirm = invitee_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": invitee_order_id, "providerTradeNo": f"manual_{invitee_order_id}"},
    )
    assert invitee_confirm.status_code == 200

    overview = admin_client.get("/api/admin/membership/overview")
    assert overview.status_code == 200
    assert overview.json()["data"]["paidOrders"] == 1
    assert overview.json()["data"]["activeMemberships"] == 1
    assert overview.json()["data"]["inviteBindings"] == 1
    assert overview.json()["data"]["rewardedInvites"] == 0
    assert overview.json()["data"]["pendingCommissionCent"] == 500
    assert overview.json()["data"]["withdrawableCommissionCent"] == 0
    assert overview.json()["data"]["coupons"] == 1
    assert overview.json()["data"]["availableCoupons"] == 1

    orders = admin_client.get(f"/api/admin/membership/orders?status=paid&userSearch={invitee_public_uid}")
    assert orders.status_code == 200
    assert len(orders.json()["data"]) == 1
    assert orders.json()["data"][0]["orderId"] == invitee_order_id
    assert orders.json()["data"][0]["orderType"] == "first_purchase"
    assert orders.json()["data"][0]["user"]["publicUid"] == invitee_public_uid

    invites = admin_client.get(f"/api/admin/membership/invites?search={inviter_public_uid}")
    assert invites.status_code == 200
    assert len(invites.json()["data"]) == 1
    assert invites.json()["data"][0]["inviter"]["publicUid"] == inviter_public_uid
    assert invites.json()["data"][0]["invitee"]["publicUid"] == invitee_public_uid
    assert invites.json()["data"][0]["status"] == "commission_pending"
    assert invites.json()["data"][0]["rewardCouponId"] is None
    discount_coupon_id = invites.json()["data"][0]["discountCouponId"]
    assert discount_coupon_id is not None
    assert invites.json()["data"][0]["commissionAmountCent"] == 500

    coupons = admin_client.get(f"/api/admin/membership/coupons?search={invitee_public_uid}&status=available")
    assert coupons.status_code == 200
    assert len(coupons.json()["data"]) == 1
    assert coupons.json()["data"][0]["couponId"] == discount_coupon_id
    assert coupons.json()["data"][0]["source"] == "invite_discount"
    assert coupons.json()["data"][0]["title"] == "邀请码 7.5 折券"
    assert coupons.json()["data"][0]["couponType"] == "percent"
    assert coupons.json()["data"][0]["discountRate"] == 75

    order_detail = admin_client.get(f"/api/admin/membership/orders/{invitee_order_id}")
    assert order_detail.status_code == 200
    detail_payload = order_detail.json()["data"]
    assert detail_payload["order"]["orderId"] == invitee_order_id
    assert detail_payload["membership"]["currentStatus"] == "active"
    assert detail_payload["payment"]["status"] == "succeeded"
    assert detail_payload["invite"]["rewardTriggeredByThisOrder"] is False
    assert detail_payload["invite"]["rewardCoupon"] is None
    assert detail_payload["invite"]["discountCoupon"]["couponId"] == discount_coupon_id
    assert detail_payload["invite"]["commission"]["commissionAmountCent"] == 500
    assert detail_payload["invite"]["commission"]["status"] == "pending"
    assert detail_payload["operations"]["canRequestRefund"] is True
    assert detail_payload["operations"]["canSyncPayment"] is False

    granted = admin_client.post(
        "/api/admin/membership/coupons/grant",
        json={
            "userId": invitee_public_uid,
            "amountCent": 800,
            "title": "后台补偿 8 元券",
            "expiresInDays": 15,
            "minSpendCent": 1490,
        },
    )
    assert granted.status_code == 200
    granted_coupon = granted.json()["data"]
    granted_coupon_id = granted_coupon["couponId"]
    assert granted_coupon["user"]["publicUid"] == invitee_public_uid
    assert granted_coupon["source"] == "admin_grant"
    assert granted_coupon["status"] == "available"

    invitee_coupons = admin_client.get(f"/api/admin/membership/coupons?search={invitee_public_uid}&status=available")
    assert invitee_coupons.status_code == 200
    invitee_coupon_ids = {item["couponId"] for item in invitee_coupons.json()["data"]}
    assert granted_coupon_id in invitee_coupon_ids
    assert any(item["source"] == "admin_grant" for item in invitee_coupons.json()["data"])

    voided = admin_client.post(
        f"/api/admin/membership/coupons/{granted_coupon_id}/void",
        json={"reason": "risk review"},
    )
    assert voided.status_code == 200
    assert voided.json()["data"]["couponId"] == granted_coupon_id
    assert voided.json()["data"]["status"] == "revoked"

    refunded = admin_client.post(
        f"/api/admin/membership/orders/{invitee_order_id}/refund",
        json={"reason": "chargeback"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["data"]["order"]["orderId"] == invitee_order_id
    assert refunded.json()["data"]["order"]["status"] == "refunded"

    activity = admin_client.get("/api/admin/activity")
    assert activity.status_code == 200
    action_types = [item["actionType"] for item in activity.json()["data"]]
    assert "membership.coupon_granted" in action_types
    assert "membership.coupon_voided" in action_types
    assert "membership.order_refunded" in action_types


def test_admin_can_settle_and_list_membership_commissions(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)
    invitee_client = TestClient(app)

    _register_user(admin_client, "admin@example.com")
    inviter_payload = _register_user(inviter_client, "inviter@example.com")
    inviter_public_uid = inviter_payload["publicUid"]
    invitee_payload = _register_user(invitee_client, "invitee@example.com", invite_code=inviter_public_uid)
    invitee_public_uid = invitee_payload["publicUid"]

    discount_coupon_id = invitee_client.get("/api/coupons/me").json()["data"][0]["couponId"]
    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2026-05-04T00:00:00+00:00")):
        created = invitee_client.post("/api/membership/orders", json={"provider": "manual_test", "couponId": discount_coupon_id})
        assert created.status_code == 200
        order_id = created.json()["data"]["order"]["orderId"]
        confirmed = invitee_client.post(
            "/api/payments/membership/callback/manual_test",
            json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
        )
    assert confirmed.status_code == 200

    pending = admin_client.get(f"/api/admin/membership/commissions?search={inviter_public_uid}")
    assert pending.status_code == 200
    assert len(pending.json()["data"]) == 1
    assert pending.json()["data"][0]["status"] == "pending"
    assert pending.json()["data"][0]["commissionAmountCent"] == 500
    assert pending.json()["data"][0]["sourceOrderId"] == order_id
    assert pending.json()["data"][0]["invitee"]["publicUid"] == invitee_public_uid

    with patch("backend.system.membership_commission_store._utc_now", return_value=datetime.fromisoformat("2026-05-05T00:00:01+00:00")):
        settled = admin_client.post("/api/admin/membership/commissions/settle")
    assert settled.status_code == 200
    assert settled.json()["data"]["settledCount"] == 1

    settled_list = admin_client.get(f"/api/admin/membership/commissions?search={inviter_public_uid}&status=settled")
    assert settled_list.status_code == 200
    assert len(settled_list.json()["data"]) == 1
    assert settled_list.json()["data"][0]["status"] == "settled"


def test_admin_can_audit_and_resolve_membership_withdrawals(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    inviter_client = TestClient(app)

    _register_user(admin_client, "admin@example.com")
    inviter_payload = _register_user(inviter_client, "inviter@example.com")
    inviter_public_uid = inviter_payload["publicUid"]

    _create_settled_invited_membership(
        app,
        admin_client,
        inviter_public_uid,
        invitee_email="invitee@example.com",
        paid_at=datetime.fromisoformat("2026-05-04T00:00:00+00:00"),
    )
    identity = _bind_manual_payout_identity(inviter_client)

    requested = inviter_client.post(
        "/api/commissions/withdrawals",
        json={"amountCent": 500},
    )
    assert requested.status_code == 200
    withdrawal_id = requested.json()["data"]["withdrawalId"]

    overview = admin_client.get("/api/admin/membership/overview")
    assert overview.status_code == 200
    assert overview.json()["data"]["withdrawals"] == 1
    assert overview.json()["data"]["reservedWithdrawalCent"] == 500
    assert overview.json()["data"]["paidOutCent"] == 0

    processing = admin_client.get(f"/api/admin/membership/withdrawals?search={inviter_public_uid}&status=processing")
    assert processing.status_code == 200
    assert len(processing.json()["data"]) == 1
    assert processing.json()["data"][0]["withdrawalId"] == withdrawal_id
    assert processing.json()["data"][0]["user"]["publicUid"] == inviter_public_uid
    assert processing.json()["data"][0]["amountCent"] == 500
    assert processing.json()["data"][0]["targetType"] == "wechat_pay"
    assert processing.json()["data"][0]["identityId"] == identity["identityId"]
    assert processing.json()["data"][0]["identityMaskedLabel"].startswith("openid_")
    assert processing.json()["data"][0]["outBillNo"].startswith("LPWD")

    identities = admin_client.get(f"/api/admin/membership/payout-identities?search={inviter_public_uid}")
    assert identities.status_code == 200
    assert len(identities.json()["data"]) == 1
    assert identities.json()["data"][0]["identityId"] == identity["identityId"]

    warning = get_membership_commission_store().create_reconciliation_warning(
        withdrawal_id,
        severity="warning",
        reason_code="stale_processing",
        message="withdrawal has stayed processing for too long",
    )
    warnings = admin_client.get("/api/admin/membership/withdrawals/warnings?status=open")
    assert warnings.status_code == 200
    assert warnings.json()["data"][0]["warningId"] == warning.warning_id

    acknowledged = admin_client.post(f"/api/admin/membership/withdrawals/warnings/{warning.warning_id}/ack", json={})
    assert acknowledged.status_code == 200
    assert acknowledged.json()["data"]["status"] == "resolved"
    assert acknowledged.json()["data"]["resolvedAt"] is not None

    resolved = admin_client.post(
        f"/api/admin/membership/withdrawals/{withdrawal_id}/resolve",
        json={"status": "succeeded", "providerTransferNo": "transfer_success_001"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "succeeded"
    assert resolved.json()["data"]["providerTransferNo"] == "transfer_success_001"

    succeeded = admin_client.get(f"/api/admin/membership/withdrawals?search={inviter_public_uid}&status=succeeded")
    assert succeeded.status_code == 200
    assert len(succeeded.json()["data"]) == 1
    assert succeeded.json()["data"][0]["status"] == "succeeded"

    overview_after = admin_client.get("/api/admin/membership/overview")
    assert overview_after.status_code == 200
    assert overview_after.json()["data"]["reservedWithdrawalCent"] == 0
    assert overview_after.json()["data"]["paidOutCent"] == 500


def test_admin_can_close_pending_membership_order(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])

    created = member_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    closed = admin_client.post(f"/api/admin/membership/orders/{order_id}/close")
    assert closed.status_code == 200
    closed_payload = closed.json()["data"]
    assert closed_payload["idempotent"] is False
    assert closed_payload["order"]["orderId"] == order_id
    assert closed_payload["order"]["status"] == "closed"
    assert closed_payload["order"]["closedAt"] is not None
    assert "closed pending membership order" in closed_payload["order"]["remark"]
    assert closed_payload["operations"]["canCloseOrder"] is False

    detail = admin_client.get(f"/api/admin/membership/orders/{order_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()["data"]
    assert detail_payload["order"]["status"] == "closed"
    assert detail_payload["operations"]["canCloseOrder"] is False

    activity = admin_client.get("/api/admin/activity")
    assert activity.status_code == 200
    action_types = [item["actionType"] for item in activity.json()["data"]]
    assert "membership.order_closed" in action_types


def test_admin_membership_refund_rejects_late_paid_order(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])

    created = member_client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    confirmed = member_client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed.status_code == 200

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        refund_attempt = admin_client.post(
            f"/api/admin/membership/orders/{order_id}/refund",
            json={"reason": "too late"},
        )

    assert refund_attempt.status_code == 400
    assert refund_attempt.json()["error"]["code"] == "PRECONDITION"
    assert refund_attempt.json()["error"]["message"] == "Membership refund period has expired."

    detail = admin_client.get(f"/api/admin/membership/orders/{order_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["order"]["status"] == "paid"
    assert detail.json()["data"]["operations"]["canRequestRefund"] is True


def test_admin_can_sync_wechat_membership_payment_and_view_detail(
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
                "transaction_id": "4200000000000000000999",
                "success_time": "2026-05-04T16:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-admin-detail"},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    detail_before = admin_client.get(f"/api/admin/membership/orders/{order_id}")
    assert detail_before.status_code == 200
    detail_before_payload = detail_before.json()["data"]
    assert detail_before_payload["payment"] is None
    assert detail_before_payload["operations"]["canSyncPayment"] is True
    assert detail_before_payload["operations"]["hasPaymentRecord"] is False

    synced = admin_client.post(f"/api/admin/membership/orders/{order_id}/sync-payment")
    assert synced.status_code == 200
    synced_payload = synced.json()["data"]
    assert synced_payload["confirmed"] is True
    assert synced_payload["order"]["status"] == "paid"
    assert synced_payload["remote"]["remoteStatus"] == "paid"
    assert synced_payload["payment"]["providerTradeNo"] == "4200000000000000000999"
    assert synced_payload["operations"]["canRequestRefund"] is True

    detail_after = admin_client.get(f"/api/admin/membership/orders/{order_id}")
    assert detail_after.status_code == 200
    detail_after_payload = detail_after.json()["data"]
    assert detail_after_payload["payment"]["status"] == "succeeded"
    assert detail_after_payload["payment"]["hasPaymentCallbackPayload"] is True
    assert detail_after_payload["membership"]["currentStatus"] == "active"
    assert detail_after_payload["operations"]["canSyncPayment"] is False


def test_admin_can_finish_refund_pending_wechat_order_after_refund_window(
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
            remote_order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": remote_order_id,
                "trade_state": "SUCCESS",
                "transaction_id": "4200000000000000000888",
                "success_time": "2026-05-04T16:00:00+08:00",
                "amount": {"total": 2000},
                "payer": {"openid": "wx-openid-admin-refund"},
            }
        if method == "POST" and uri == "/v3/refund/domestic/refunds":
            assert body is not None
            refund_order_id = str(body["out_refund_no"]).removeprefix("mrefund_")
            return {
                "out_trade_no": refund_order_id,
                "out_refund_no": f"mrefund_{refund_order_id}",
                "refund_id": "5000000000000000000888",
                "status": "PROCESSING",
                "amount": {"refund": 2000},
            }
        if method == "GET" and "/v3/refund/domestic/refunds/" in uri:
            refund_order_id = order_id
            return {
                "out_trade_no": refund_order_id,
                "out_refund_no": f"mrefund_{refund_order_id}",
                "refund_id": "5000000000000000000888",
                "status": "SUCCESS",
                "success_time": "2099-01-01T00:00:00+00:00",
                "amount": {"refund": 2000},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    synced_payment = admin_client.post(f"/api/admin/membership/orders/{order_id}/sync-payment")
    assert synced_payment.status_code == 200
    assert synced_payment.json()["data"]["order"]["status"] == "paid"

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2026-05-04T08:30:00+00:00")):
        requested_refund = admin_client.post(
            f"/api/admin/membership/orders/{order_id}/refund",
            json={"reason": "wechat refund request"},
        )
    assert requested_refund.status_code == 200
    assert requested_refund.json()["data"]["order"]["status"] == "refund_pending"

    with patch("backend.system.membership_store._utc_now", return_value=datetime.fromisoformat("2099-01-01T00:00:00+00:00")):
        synced_refund = admin_client.post(
            f"/api/admin/membership/orders/{order_id}/refund",
            json={"reason": "wechat refund request"},
        )

    assert synced_refund.status_code == 200
    assert synced_refund.json()["data"]["order"]["status"] == "refunded"
    assert synced_refund.json()["data"]["remoteStatus"] == "refunded"


def test_admin_can_sync_closed_wechat_order_and_view_failure_detail(
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
            return {"code_url": "weixin://wxpay/bizpayurl/up?pr=fake-wechat-native-closed"}
        if method == "GET" and "/v3/pay/transactions/out-trade-no/" in uri:
            order_id = uri.split("/out-trade-no/", 1)[1].split("?", 1)[0]
            return {
                "out_trade_no": order_id,
                "trade_state": "CLOSED",
                "transaction_id": "4200000000000000000998",
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = _register_user(admin_client, "admin@example.com")
    _register_user(member_client, "member@example.com", invite_code=admin_register["publicUid"])

    created = member_client.post("/api/membership/orders", json={"provider": "wechat_native"})
    assert created.status_code == 200
    order_id = created.json()["data"]["order"]["orderId"]

    synced = admin_client.post(f"/api/admin/membership/orders/{order_id}/sync-payment")
    assert synced.status_code == 200
    synced_payload = synced.json()["data"]
    assert synced_payload["confirmed"] is False
    assert synced_payload["order"]["status"] == "closed"
    assert synced_payload["order"]["remark"] == "remote payment state: closed"
    assert synced_payload["remote"]["remoteStatus"] == "closed"
    assert synced_payload["payment"]["status"] == "failed"
    assert synced_payload["operations"]["canSyncPayment"] is False
    assert synced_payload["operations"]["canCloseOrder"] is False

    detail = admin_client.get(f"/api/admin/membership/orders/{order_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()["data"]
    assert detail_payload["order"]["status"] == "closed"
    assert detail_payload["payment"]["status"] == "failed"
    assert detail_payload["payment"]["providerTradeNo"] == "4200000000000000000998"
    assert detail_payload["membership"]["currentStatus"] == "never_purchased"
    assert detail_payload["operations"]["canSyncPayment"] is False
    assert detail_payload["operations"]["canCloseOrder"] is False
