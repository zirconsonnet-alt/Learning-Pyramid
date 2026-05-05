# 学习金字塔 Frontend

The frontend is built with React + Vite and is served by the FastAPI backend in release mode.

Common commands:

```powershell
pnpm install
pnpm build
pnpm dev
```

Project-level release and runtime instructions live in the repository root [README](../README.md).

## WeChat payout verification

Desktop users bind a receiving identity from the membership page by opening a QR modal; the QR points to the public backend entry `/api/commissions/payout-identity/wechat/mobile-bind?attempt=...&state=...`. Mobile WeChat scans that one-time URL, the backend validates the desktop attempt, redirects through WeChat OAuth, and then lands on `/membership/wechat-payout-bind` so the user can confirm the LearningPyramid account before binding. The user does not need to log in to LearningPyramid on the phone.

Commission withdrawal confirmation must be tested inside a supported WeChat client when production merchant transfer is enabled. The frontend calls `WeixinJSBridge.invoke("requestMerchantTransfer", ...)` only when the backend returns a confirmation package; that callback means the user confirmation UI returned, not that the transfer has succeeded.

Final withdrawal state still comes from `/api/payments/wechat/transfer-notify` or `tools/reconcile_commission_withdrawals.py`. For local development, keep `PLM_ENABLE_MANUAL_TEST_PAYMENT=true` and use the `manual_test` binding/withdrawal path instead of a real WeChat client.
