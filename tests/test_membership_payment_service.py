import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError

from adapter.schemas import StartWeChatWithdrawalConfirmationAttemptRequest
from adapter.routers.membership import _desktop_withdrawal_confirmation_url
from backend.system.membership_payment_service import MembershipPaymentService


class MembershipPaymentServiceTest(unittest.TestCase):
    def test_wechat_native_payment_payload_uses_fast_automatic_polling_copy(self) -> None:
        class Order:
            provider = "wechat_native"
            order_id = "mord_e2e"
            order_type = "renewal"
            payable_amount_cent = 2000
            expired_at = None

        env = {
            "LEARNINGPYRAMID_WECHAT_PAY_APP_ID": "wx_app",
            "LEARNINGPYRAMID_WECHAT_PAY_MCH_ID": "mch_123",
            "LEARNINGPYRAMID_WECHAT_PAY_CERT_SERIAL_NO": "cert_123",
            "LEARNINGPYRAMID_WECHAT_PAY_API_V3_KEY": "1" * 32,
            "LEARNINGPYRAMID_WECHAT_PAY_PRIVATE_KEY_PEM_PATH": "private.pem",
            "LEARNINGPYRAMID_WECHAT_PAY_PUBLIC_KEY_ID": "pub_key",
            "LEARNINGPYRAMID_WECHAT_PAY_PUBLIC_KEY_PEM_PATH": "public.pem",
        }

        with (
            patch("backend.system.membership_payment_service._safe_path", return_value=Path(__file__).resolve()),
            patch("backend.system.membership_payment_service.os.getenv", side_effect=lambda key, default=None: env.get(key, default)),
            patch.object(MembershipPaymentService, "_wechat_request_json", return_value={"code_url": "weixin://wxpay/bizpayurl?pr=e2e"}),
            patch.object(MembershipPaymentService, "_build_qr_image_data_url", return_value="data:image/png;base64,e2e"),
        ):
            payload = MembershipPaymentService().create_payment_payload(Order(), client_ip="127.0.0.1", public_origin="https://example.test")

        self.assertEqual(payload.poll_interval_seconds, 2)
        self.assertIn("页面会自动刷新", payload.instruction)
        self.assertNotIn("手动点击同步支付状态", payload.instruction)

    def test_desktop_wechat_payout_scan_url_uses_confirm_route(self) -> None:
        url = _desktop_withdrawal_confirmation_url(
            "https://plm.example.test/membership?from=desktop",
            confirmation_attempt_id="confirm_1",
            state="state_1",
        )

        self.assertEqual("https://plm.example.test/membership/wechat-payout-confirm?attempt=confirm_1&state=state_1", url)
        self.assertNotIn("wechat-payout-bind", url)

    def test_wechat_payout_scan_requires_positive_withdrawal_amount(self) -> None:
        with self.assertRaises(ValidationError):
            StartWeChatWithdrawalConfirmationAttemptRequest(returnUrl="/membership", amountCent=0)


if __name__ == "__main__":
    unittest.main()
