from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from adapter.deps import get_api, get_auth_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
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


def test_admin_can_manage_users_and_groups(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    assert admin_register.json()["data"]["roles"] == ["super_admin"]

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_user_id = member_register.json()["data"]["userId"]

    granted = admin_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": True},
    )
    assert granted.status_code == 200
    assert "admin" in granted.json()["data"]["roles"]

    member_overview = member_client.get("/api/admin/overview")
    assert member_overview.status_code == 200

    forbidden_role_update = member_client.patch(
        f"/api/admin/users/{member_user_id}/roles",
        json={"role": "admin", "enabled": False},
    )
    assert forbidden_role_update.status_code == 403
    assert forbidden_role_update.json()["error"]["message"] == "Super administrator access required"

    created_group = member_client.post(
        "/api/study-groups",
        json={
            "name": "Admin Target Group",
            "description": "等待后台管理操作",
            "visibility": "public",
            "joinPolicy": "free",
        },
    )
    group_id = created_group.json()["data"]["groupId"]

    post = member_client.post(
        f"/api/study-groups/{group_id}/posts",
        json={"kind": "discussion", "content": "这是一条需要后台能看到的动态。"},
    )
    assert post.status_code == 200
    post_id = post.json()["data"]["postId"]

    comment = member_client.post(
        f"/api/study-groups/{group_id}/posts/{post_id}/comments",
        json={"content": "这是一条需要后台能处理的评论。"},
    )
    assert comment.status_code == 200
    comment_id = comment.json()["data"]["commentId"]

    overview = admin_client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["data"]["users"] == 2
    assert overview.json()["data"]["groups"] == 1
    assert overview.json()["data"]["posts"] == 1
    assert overview.json()["data"]["comments"] == 1

    users = admin_client.get("/api/admin/users")
    assert users.status_code == 200
    payload_by_id = {item["userId"]: item for item in users.json()["data"]}
    assert payload_by_id[member_user_id]["status"] == "active"

    user_detail = admin_client.get(f"/api/admin/users/{member_user_id}")
    assert user_detail.status_code == 200
    assert user_detail.json()["data"]["userId"] == member_user_id
    assert user_detail.json()["data"]["groups"][0]["groupId"] == group_id
    assert user_detail.json()["data"]["groups"][0]["memberRole"] == "owner"

    suspended = admin_client.patch(f"/api/admin/users/{member_user_id}/status", json={"status": "suspended"})
    assert suspended.status_code == 200
    assert suspended.json()["data"]["status"] == "suspended"

    denied = member_client.get("/api/study-groups")
    assert denied.status_code == 401
    assert denied.json()["error"]["message"] == "Authentication required"

    archived = admin_client.patch(f"/api/admin/groups/{group_id}/status", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    group_detail = admin_client.get(f"/api/admin/groups/{group_id}")
    assert group_detail.status_code == 200
    assert group_detail.json()["data"]["groupId"] == group_id
    assert group_detail.json()["data"]["members"][0]["userId"] == member_user_id
    assert group_detail.json()["data"]["posts"][0]["postId"] == post_id
    assert group_detail.json()["data"]["comments"][0]["commentId"] == comment_id

    admin_posts = admin_client.get("/api/admin/content/posts")
    assert admin_posts.status_code == 200
    assert admin_posts.json()["data"][0]["postId"] == post_id

    admin_comments = admin_client.get("/api/admin/content/comments")
    assert admin_comments.status_code == 200
    assert admin_comments.json()["data"][0]["commentId"] == comment_id

    deleted_comment = admin_client.delete(f"/api/admin/content/comments/{comment_id}")
    assert deleted_comment.status_code == 200
    assert deleted_comment.json()["data"]["commentId"] == comment_id

    deleted_post = admin_client.delete(f"/api/admin/content/posts/{post_id}")
    assert deleted_post.status_code == 200
    assert deleted_post.json()["data"]["postId"] == post_id

    activity = admin_client.get("/api/admin/activity")
    assert activity.status_code == 200
    action_types = [item["actionType"] for item in activity.json()["data"]]
    assert "user.role_updated" in action_types
    assert "user.status_updated" in action_types
    assert "group.status_updated" in action_types
    assert "content.comment_deleted" in action_types
    assert "content.post_deleted" in action_types

    audit_logs = admin_client.get("/api/admin/audit-logs")
    assert audit_logs.status_code == 200
    assert [item["actionType"] for item in audit_logs.json()["data"]] == action_types


def test_non_admin_cannot_access_admin_endpoints(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    normal_client = TestClient(app)

    admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    normal_client.post("/api/auth/register", json={"email": "normal@example.com", "password": "password123"})

    denied = normal_client.get("/api/admin/overview")
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "Administrator access required"


def test_admin_user_role_filter(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    role_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200
    admin_user_id = admin_register.json()["data"]["userId"]

    role_register = role_client.post("/api/auth/register", json={"email": "role@example.com", "password": "password123"})
    assert role_register.status_code == 200
    role_user_id = role_register.json()["data"]["userId"]

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200
    member_user_id = member_register.json()["data"]["userId"]

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

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    inviter_register = inviter_client.post("/api/auth/register", json={"email": "inviter@example.com", "password": "password123"})
    assert inviter_register.status_code == 200
    inviter_payload = inviter_register.json()["data"]
    inviter_public_uid = inviter_payload["publicUid"]

    invitee_register = invitee_client.post(
        "/api/auth/register",
        json={"email": "invitee@example.com", "password": "password123", "inviteCode": inviter_public_uid},
    )
    assert invitee_register.status_code == 200
    invitee_payload = invitee_register.json()["data"]
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
    assert overview.json()["data"]["rewardedInvites"] == 1
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
    assert invites.json()["data"][0]["status"] == "rewarded"
    reward_coupon_id = invites.json()["data"][0]["rewardCouponId"]
    assert reward_coupon_id is not None

    coupons = admin_client.get(f"/api/admin/membership/coupons?search={inviter_public_uid}&status=available")
    assert coupons.status_code == 200
    assert len(coupons.json()["data"]) == 1
    assert coupons.json()["data"][0]["couponId"] == reward_coupon_id
    assert coupons.json()["data"][0]["source"] == "invite_reward"
    assert coupons.json()["data"][0]["title"] == "邀请奖励 5 元券"

    order_detail = admin_client.get(f"/api/admin/membership/orders/{invitee_order_id}")
    assert order_detail.status_code == 200
    detail_payload = order_detail.json()["data"]
    assert detail_payload["order"]["orderId"] == invitee_order_id
    assert detail_payload["membership"]["currentStatus"] == "active"
    assert detail_payload["payment"]["status"] == "succeeded"
    assert detail_payload["invite"]["rewardTriggeredByThisOrder"] is True
    assert detail_payload["invite"]["rewardCoupon"]["couponId"] == reward_coupon_id
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


def test_admin_can_close_pending_membership_order(auth_env: None) -> None:
    app = create_app()
    admin_client = TestClient(app)
    member_client = TestClient(app)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

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
                "success_time": "2026-03-26T16:00:00+08:00",
                "amount": {"total": 1490},
                "payer": {"openid": "wx-openid-admin-detail"},
            }
        raise AssertionError(f"unexpected wechat request: {method} {uri}")

    monkeypatch.setattr(payment_service, "_wechat_request_json", fake_wechat_request_json)

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

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

    admin_register = admin_client.post("/api/auth/register", json={"email": "admin@example.com", "password": "password123"})
    assert admin_register.status_code == 200

    member_register = member_client.post("/api/auth/register", json={"email": "member@example.com", "password": "password123"})
    assert member_register.status_code == 200

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
