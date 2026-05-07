from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "profile" / "ProfilePage.tsx"
MEMBERSHIP_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "membership" / "MembershipPage.tsx"
WECHAT_PAYOUT_BINDING_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "membership" / "WechatPayoutBindingPage.tsx"
MEMBERSHIP_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "membership.ts"


def test_profile_learning_view_removes_extra_chart_capsule() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")
    learning_curve_source = source[source.index("function LearningCurve"):source.index("export function ProfilePage")]

    assert '<div className="space-y-4">' in learning_curve_source
    assert 'className="theme-soft-surface rounded-[1.6rem] p-5"' not in learning_curve_source


def test_membership_invite_code_card_uses_compact_width() -> None:
    source = MEMBERSHIP_PAGE.read_text(encoding="utf-8")

    assert 'className="flex w-full max-w-[22rem] flex-col gap-3 md:w-auto"' in source
    assert 'className="flex min-w-[18rem] max-w-xl flex-col gap-3"' not in source


def test_membership_withdrawal_uses_one_scan_flow_without_identity_capsule() -> None:
    source = MEMBERSHIP_PAGE.read_text(encoding="utf-8")

    assert "微信收款身份</div>" not in source
    assert "提现前需要先绑定微信收款身份" not in source
    assert "payoutReadiness?.status !== \"ready\"" in source
    assert "amountCent," in source
    assert "<DialogTitle>微信扫码确认提现</DialogTitle>" in source


def test_wechat_payout_binding_page_supports_withdrawal_confirmation_flow() -> None:
    source = WECHAT_PAYOUT_BINDING_PAGE.read_text(encoding="utf-8")

    assert "确认微信提现" in source
    assert "确认并提现" in source
    assert "requestMerchantTransfer" in source
    assert "formatMembershipPrice(withdrawalAmountCent)" in source


def test_membership_api_exposes_one_scan_withdrawal_attempt_payload() -> None:
    source = MEMBERSHIP_API.read_text(encoding="utf-8")

    assert "amountCent: z.number().default(0)" in source
    assert "withdrawal: CommissionWithdrawalSchema.optional()" in source
    assert "PayoutIdentityDetailSchema" in source


def test_membership_purchase_dialog_supports_graduate_exam_plan() -> None:
    dialog = REPO_ROOT / "frontend" / "src" / "views" / "membership" / "components" / "MembershipPurchaseDialog.tsx"
    dialog_source = dialog.read_text(encoding="utf-8")
    page_source = MEMBERSHIP_PAGE.read_text(encoding="utf-8")
    api_source = MEMBERSHIP_API.read_text(encoding="utf-8")

    assert 'planId: "graduate_exam"' in dialog_source
    assert 'title: "考研套餐"' in dialog_source
    assert "购买当天算到同年 12 月 21 日" in dialog_source
    assert "会员时长：{preview?.periodDays ?? pendingOrder?.periodDays ?? 30} 天" in dialog_source
    assert "套餐类型：{preview?.planName ?? pendingOrder?.planName ?? \"月会员\"}" in dialog_source
    assert "const [selectedPlanId, setSelectedPlanId] = useState(DEFAULT_MEMBERSHIP_PLAN_ID)" in page_source
    assert "const effectiveSelectedPlanId = pendingOrder?.planId || selectedPlanId" in page_source
    assert "planId: effectiveSelectedPlanId" in page_source
    assert "planId: z.string()" in api_source
