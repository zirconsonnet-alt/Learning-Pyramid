from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.errors import PreconditionFailure
from backend.system.membership_payment_service import (
    PayoutConfirmationPayload,
    MembershipPaymentService,
)


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "{}", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = headers or {}

    def json(self) -> dict[str, object]:
        return {"code_url": "weixin://wxpay/bizpayurl?pr=test"}


def _enable_wechat_native(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_key_path = tmp_path / "wechat-apiclient-key.pem"
    public_key_path = tmp_path / "wechatpay-public.pem"
    private_key_path.write_text("test-private-key")
    public_key_path.write_text("test-public-key")
    monkeypatch.setenv("PLM_WECHAT_PAY_APP_ID", "wx-test-app")
    monkeypatch.setenv("PLM_WECHAT_PAY_MCH_ID", "1900000109")
    monkeypatch.setenv("PLM_WECHAT_PAY_CERT_SERIAL_NO", "SERIALNO1234567890")
    monkeypatch.setenv("PLM_WECHAT_PAY_API_V3_KEY", "0123456789ABCDEF0123456789ABCDEF")
    monkeypatch.setenv("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH", str(private_key_path))
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_ID", "PUB_KEY_ID_TEST")
    monkeypatch.setenv("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH", str(public_key_path))


def test_wechat_request_json_retries_once_after_signature_verification_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    service = MembershipPaymentService()
    attempts = {"request": 0, "verify": 0}

    def fake_request(method: str, url: str, *, data: bytes | None, headers: dict[str, str], timeout: float) -> _FakeResponse:
        attempts["request"] += 1
        return _FakeResponse(
            text='{"code_url":"weixin://wxpay/bizpayurl?pr=test"}',
            headers={
                "Wechatpay-Signature": "WECHATPAY/SIGNTEST/test-signature",
                "Wechatpay-Serial": "PUB_KEY_ID_TEST",
                "Wechatpay-Signature-Type": "WECHATPAY2-SHA256-RSA2048",
            },
        )

    def fake_verify(*, headers: dict[str, str], body_text: str | None = None, body_bytes: bytes | None = None) -> None:
        attempts["verify"] += 1
        assert body_bytes == b'{"code_url":"weixin://wxpay/bizpayurl?pr=test"}'
        if attempts["verify"] == 1:
            raise PreconditionFailure("wechat payment signature verification failed")

    monkeypatch.setattr(service, "_build_wechat_authorization", lambda method, uri, body_text: "AUTH")
    monkeypatch.setattr(service._session, "request", fake_request)
    monkeypatch.setattr(service, "_verify_wechat_signature", fake_verify)

    payload = service._wechat_request_json("POST", "/v3/pay/transactions/native", {"foo": "bar"})

    assert payload["code_url"] == "weixin://wxpay/bizpayurl?pr=test"
    assert attempts == {"request": 2, "verify": 2}


def test_wechat_request_json_returns_payload_after_repeated_signature_verification_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    service = MembershipPaymentService()
    attempts = {"request": 0, "verify": 0}

    def fake_request(method: str, url: str, *, data: bytes | None, headers: dict[str, str], timeout: float) -> _FakeResponse:
        attempts["request"] += 1
        return _FakeResponse(
            text='{"code_url":"weixin://wxpay/bizpayurl?pr=test"}',
            headers={
                "Wechatpay-Signature": "test-signature",
                "Wechatpay-Serial": "PUB_KEY_ID_TEST",
                "Wechatpay-Signature-Type": "WECHATPAY2-SHA256-RSA2048",
            },
        )

    def fake_verify(*, headers: dict[str, str], body_text: str | None = None, body_bytes: bytes | None = None) -> None:
        attempts["verify"] += 1
        raise PreconditionFailure("wechat payment signature verification failed")

    monkeypatch.setattr(service, "_build_wechat_authorization", lambda method, uri, body_text: "AUTH")
    monkeypatch.setattr(service._session, "request", fake_request)
    monkeypatch.setattr(service, "_verify_wechat_signature", fake_verify)

    payload = service._wechat_request_json("POST", "/v3/pay/transactions/native", {"foo": "bar"})

    assert payload["code_url"] == "weixin://wxpay/bizpayurl?pr=test"
    assert attempts == {"request": 2, "verify": 2}


def test_get_wechat_public_key_loads_once_and_caches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    service = MembershipPaymentService()
    sentinel = object()
    calls = {"count": 0}

    def fake_load_pem_public_key(raw: bytes):
        calls["count"] += 1
        assert raw == b"test-public-key"
        return sentinel

    monkeypatch.setattr("backend.system.membership_payment_service.serialization.load_pem_public_key", fake_load_pem_public_key)

    assert service._get_wechat_public_key() is sentinel
    assert service._get_wechat_public_key() is sentinel
    assert calls["count"] == 1


class _Withdrawal:
    withdrawal_id = "mwd_test_001"
    user_id = "user_inviter"
    amount_cent = 500
    wechat_open_id = "openid_inviter_001"
    out_bill_no = "LPWD202605050001"


def test_wechat_payout_config_reads_provider_mode_and_binding_qr_ttl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    monkeypatch.setenv("PLM_WECHAT_PAY_TRANSFER_SCENE_ID", "1001")
    monkeypatch.setenv("PLM_WECHAT_PAY_PAYOUT_PROVIDER_MODE", "disabled")
    monkeypatch.setenv("PLM_WECHAT_PAY_BINDING_QR_TTL_MINUTES", "15")

    config = MembershipPaymentService().current_wechat_payout_config()

    assert config.provider_mode == "disabled"
    assert config.binding_qr_ttl_minutes == 15
    assert config.enabled is False


def test_wechat_merchant_transfer_wait_user_confirm_maps_confirmation_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    monkeypatch.setenv("PLM_WECHAT_PAY_TRANSFER_SCENE_ID", "1001")
    service = MembershipPaymentService()
    captured: dict[str, object] = {}

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        captured["method"] = method
        captured["uri"] = uri
        captured["body"] = body or {}
        return {
            "out_bill_no": "LPWD202605050001",
            "transfer_bill_no": "133000007110099999118202605050001",
            "state": "WAIT_USER_CONFIRM",
            "package_info": "merchant-transfer-package",
        }

    monkeypatch.setattr(service, "_wechat_request_json", fake_wechat_request_json)

    result = service.request_commission_payout(_Withdrawal())

    assert captured["uri"] == "/v3/fund-app/mch-transfer/transfer-bills"
    assert captured["body"]["out_bill_no"] == "LPWD202605050001"
    assert captured["body"]["openid"] == "openid_inviter_001"
    assert result.remote_status == "awaiting_confirmation"
    assert result.provider_state == "WAIT_USER_CONFIRM"
    assert result.provider_transfer_no == "133000007110099999118202605050001"
    assert result.confirmation == PayoutConfirmationPayload(
        mode="wechat_jsapi_requestMerchantTransfer",
        mch_id="1900000109",
        app_id="wx-test-app",
        package_info="merchant-transfer-package",
    )


def test_wechat_merchant_transfer_query_maps_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    monkeypatch.setenv("PLM_WECHAT_PAY_TRANSFER_SCENE_ID", "1001")
    service = MembershipPaymentService()

    def fake_wechat_request_json(method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        assert method == "GET"
        assert "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/LPWD202605050001" in uri
        return {
            "out_bill_no": "LPWD202605050001",
            "transfer_bill_no": "133000007110099999118202605050001",
            "state": "FAIL",
            "fail_reason": "ACCOUNT_FROZEN",
            "transfer_amount": 500,
        }

    monkeypatch.setattr(service, "_wechat_request_json", fake_wechat_request_json)

    result = service.query_commission_payout("LPWD202605050001")

    assert result.remote_status == "failed"
    assert result.provider_state == "FAIL"
    assert result.failure_reason == "ACCOUNT_FROZEN"
    assert result.amount_cent == 500


def test_wechat_merchant_transfer_notification_maps_terminal_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_wechat_native(monkeypatch, tmp_path)
    monkeypatch.setenv("PLM_WECHAT_PAY_TRANSFER_SCENE_ID", "1001")
    service = MembershipPaymentService()

    monkeypatch.setattr(service, "_verify_wechat_signature", lambda *, headers, body_text: None)
    monkeypatch.setattr(
        service,
        "_decrypt_wechat_resource",
        lambda resource: {
            "out_bill_no": "LPWD202605050001",
            "transfer_bill_no": "133000007110099999118202605050001",
            "state": "SUCCESS",
            "transfer_amount": 500,
            "appid": "wx-test-app",
        },
    )

    result = service.parse_transfer_notification(
        headers={"wechatpay-serial": "PUB_KEY_ID_TEST"},
        body_text='{"id":"evt_transfer_001","resource":{"ciphertext":"encrypted"}}',
    )

    assert result.out_bill_no == "LPWD202605050001"
    assert result.provider_transfer_no == "133000007110099999118202605050001"
    assert result.remote_status == "succeeded"
    assert result.provider_state == "SUCCESS"
    assert result.amount_cent == 500
    assert result.appid == "wx-test-app"
