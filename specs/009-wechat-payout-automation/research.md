# Research: WeChat Payout Automation

## Decision: Receiving identity must be bound through WeChat authorization

**Rationale**: WeChat merchant transfer requires the payee OpenID under the merchant AppID. Letting users type OpenID is unsafe, unverifiable, and confusing. The production path should obtain the identifier through an official WeChat authorization flow and bind it to the current logged-in user. The backend stores the payout target, returns only masked labels to user/admin views, and rejects withdrawals when no active identity exists.

**Sources**:

- WeChat Pay merchant transfer "Create transfer bill": https://pay.wechatpay.cn/doc/v3/merchant/4012716434
- WeChat official account webpage authorization: https://developers.weixin.qq.com/doc/offiaccount/OA_Web_Apps/Wechat_webpage_authorization.html

**Alternatives considered**:

- Keep `wechatOpenId` in the withdrawal form: rejected because the platform cannot prove ownership and users generally do not know their OpenID.
- Let admins enter OpenID for users: rejected for normal production flow because it creates support burden and higher payout risk.
- Bind UnionID instead of OpenID only: rejected because merchant transfer requires OpenID for the payout AppID context; UnionID can be useful for correlation but cannot replace the transfer payee identifier.

## Decision: Desktop web binding uses a short-lived QR handoff to mobile WeChat

**Rationale**: The product is primarily used from a desktop web browser, which cannot directly prove the WeChat identity of the person sitting at the computer. The desktop page should create a short-lived binding attempt and display a QR code that opens a platform binding URL in mobile WeChat. The mobile WeChat page then performs official WeChat authorization, shows which LearningPyramid account is being bound, and requires an explicit confirmation before the backend activates the receiving identity. The desktop page polls the attempt and updates to ready when binding completes.

**Sources**:

- WeChat official account webpage authorization: https://developers.weixin.qq.com/doc/offiaccount/OA_Web_Apps/Wechat_webpage_authorization.html

**Alternatives considered**:

- Ask desktop users to manually paste an OpenID: rejected because users do not know the value and the platform cannot verify ownership.
- Require users to first open the full LearningPyramid web app inside WeChat: rejected because the primary product surface is desktop web and this creates a confusing detour.
- Bind immediately when the QR is scanned: rejected because a scan only proves the link was opened; the user still needs to see and confirm the platform account being bound.
- Use a payment collection QR code: rejected because binding is an identity proof flow, not a money transfer or collection action.

## Decision: Use WeChat Pay merchant transfer user-confirmation mode for production payouts

**Rationale**: Official WeChat Pay merchant transfer documentation describes the user-confirmation transfer creation endpoint as `POST /v3/fund-app/mch-transfer/transfer-bills`. It requires fields such as `appid`, `out_bill_no`, `transfer_scene_id`, `openid`, `transfer_amount`, `transfer_remark`, and scene report info, with amount in cents and a unique merchant bill number. The current code path uses the older batch transfer endpoint for commission payout; production payout should move to the merchant transfer bill flow so the user can confirm receipt in WeChat and the platform can track the transfer bill lifecycle.

**Sources**:

- WeChat Pay merchant transfer "Create transfer bill": https://pay.wechatpay.cn/doc/v3/merchant/4012716434

**Alternatives considered**:

- Continue using `/v3/transfer/batches`: rejected for the final user withdrawal experience because this feature requires user confirmation and bill-level result reconciliation.
- Mark withdrawals paid locally without provider confirmation: rejected because it breaks financial correctness.
- Use coupons or internal balance only: rejected because the user explicitly wants withdrawal to WeChat.

## Decision: Local withdrawal state must support awaiting user confirmation

**Rationale**: WeChat returns transfer bill states, and `WAIT_USER_CONFIRM` means the bill was created and the user should be guided to confirm receipt. The frontend must receive the confirmation package and call WeChat's `requestMerchantTransfer` in a supported WeChat client environment. The callback from `requestMerchantTransfer` cannot be treated as final payout success; final state still comes from WeChat notification or query.

**Sources**:

- WeChat Pay merchant transfer creation state notes: https://pay.wechatpay.cn/doc/v3/merchant/4012716434
- WeChat Pay JSAPI `requestMerchantTransfer`: https://pay.wechatpay.cn/doc/v3/merchant/4012716430

**Alternatives considered**:

- Keep only `pending`, `processing`, `succeeded`, `failed`: rejected because it cannot represent "created and waiting for user confirmation".
- Treat JSAPI success as payout success: rejected because the official JSAPI example notes that returning `ok` from the page does not itself prove funds were paid.

## Decision: Notifications are primary; merchant-bill query is the fallback

**Rationale**: WeChat Pay sends merchant transfer notifications when a transfer reaches terminal states. The documentation states terminal notification statuses include success, cancelled, and fail, and also warns that duplicate notifications can occur. It further instructs merchants to query the order if callbacks do not arrive after all notification attempts. Therefore the system needs both a public HTTPS notification endpoint and a scheduled query reconciliation path.

**Sources**:

- WeChat Pay merchant transfer callback notification: https://pay.wechatpay.cn/doc/v3/merchant/4012712115
- WeChat Pay transfer query by merchant bill number: https://pay.wechatpay.cn/doc/v3/merchant/4012716437

**Alternatives considered**:

- Notification only: rejected because missed callbacks can leave withdrawals stuck.
- Polling only: rejected because it adds unnecessary provider load and delays final state updates.
- Manual admin resolution only: rejected because the feature goal is unattended operation.

## Decision: Never change merchant bill number until the original result is known

**Rationale**: WeChat documentation warns not to replace the merchant bill number immediately after errors or unknown results because that can create duplicate transfer risk. The local withdrawal request should have a stable `out_bill_no`; retries should query or retry the original bill until its result is clear. Only a clearly failed original bill can be retried with a new local/provider attempt, and that retry must be auditable.

**Sources**:

- WeChat Pay merchant transfer retry warning: https://pay.wechatpay.cn/doc/v3/merchant/4012716434
- WeChat Pay merchant bill query retry warning: https://pay.wechatpay.cn/doc/v3/merchant/4012716437

**Alternatives considered**:

- Generate a new bill number for every retry: rejected because it can duplicate payouts.
- Let the frontend retry payout submission directly: rejected because payout retries must be controlled by backend ledger state.

## Decision: Commission settlement automation is a local maintenance batch

**Rationale**: WeChat Pay does not settle invite commission after the refund window; that is local business accounting. The existing commission store already has idempotent settlement logic and the project already has a maintenance pattern for reconciling pending WeChat payments. This feature should add a `settle_membership_commissions` maintenance function and CLI script so deployment can run it every few minutes through cron, systemd timer, hosted scheduler, or another external scheduler.

**Alternatives considered**:

- Run settlement only through the admin endpoint: rejected because it is not unattended.
- Start an in-process background loop inside FastAPI: rejected for hosted/self-hosted reliability because multiple app workers can duplicate work and process lifetime is not guaranteed.
- Ask WeChat to settle commission: rejected because WeChat is only involved in external payment/refund/payout, not the platform's local invite commission ledger.

## Decision: Preserve `manual_test` for local verification

**Rationale**: Real WeChat merchant transfer needs merchant capability, public HTTPS callback URLs, certificates/public keys, a payout scene, and WeChat client confirmation. Local tests should still be able to exercise ledger transitions through `manual_test`, but production behavior must not expose raw OpenID entry or pretend manual resolution is the normal path.

**Alternatives considered**:

- Require real WeChat config for all tests: rejected because it blocks deterministic automated tests.
- Remove manual admin resolution entirely: rejected because finance/support still need exception handling for disputed or stuck records.
