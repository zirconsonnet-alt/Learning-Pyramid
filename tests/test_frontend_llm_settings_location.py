from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "GlobalSettingsPage.tsx"
PROJECT_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "ProjectSettingsPage.tsx"
APP_SHELL = REPO_ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
AI_CHAT_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"
MEMBERSHIP_UI = REPO_ROOT / "frontend" / "src" / "views" / "membership" / "membershipUi.tsx"
HTTP_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "http.ts"
MEMBERSHIP_QUERIES = REPO_ROOT / "frontend" / "src" / "ui" / "queries" / "membership.ts"
ADMIN_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "admin.ts"
ADMIN_QUERIES = REPO_ROOT / "frontend" / "src" / "ui" / "queries" / "admin.ts"
ADMIN_MEMBERSHIP_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "admin" / "AdminMembershipPage.tsx"
LLM_SETTINGS_CARDS = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "components" / "LlmSettingsCards.tsx"
PROJECTS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "projects" / "ProjectsPage.tsx"
SUBJECTS_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "subjects.ts"
SUBJECT_DASHBOARD_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "subjects" / "SubjectDashboardPage.tsx"


def test_llm_settings_live_in_global_settings_below_access_center() -> None:
    global_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "useMyLlmSettings" in global_source
    assert "useGlobalLlmSettings" in global_source
    assert "大模型配置" in global_source
    assert "UserLlmSettingsCard" in global_source
    assert "GlobalLlmSettingsCard" in global_source
    assert "新建项目默认复习模板" not in global_source
    assert "默认复习模板" not in global_source


def test_project_settings_no_longer_owns_llm_configuration() -> None:
    project_source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "useMyLlmSettings" not in project_source
    assert "useGlobalLlmSettings" not in project_source
    assert "UserLlmSettingsCard" not in project_source
    assert "GlobalLlmSettingsCard" not in project_source
    assert 'title="AI 设置"' not in project_source


def test_ai_chat_empty_llm_notice_points_to_global_settings() -> None:
    ai_chat_source = AI_CHAT_PAGE.read_text(encoding="utf-8")

    assert "请先到项目设置里的" not in ai_chat_source
    assert "前往项目设置" not in ai_chat_source
    assert "全局设置里的“大模型配置”" in ai_chat_source
    assert "前往全局设置" in ai_chat_source


def test_member_only_helpers_are_shared_for_protected_frontend_gates() -> None:
    http_source = HTTP_API.read_text(encoding="utf-8")
    membership_ui_source = MEMBERSHIP_UI.read_text(encoding="utf-8")

    assert "MEMBER_ONLY_ERROR_MESSAGE" in http_source
    assert "isMemberOnlyApiError" in http_source
    assert "MEMBERSHIP_CENTER_PATH" in http_source
    assert "MemberOnlyFeatureNotice" in membership_ui_source
    assert "会员专属功能" in membership_ui_source
    assert "前往会员中心" in membership_ui_source


def test_llm_settings_gate_uses_membership_summary_and_preserves_member_controls() -> None:
    global_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "useMembershipSummary" in global_source
    assert "MemberOnlyFeatureNotice" in global_source
    assert "llmSettingsMemberBlocked" in global_source
    assert "llmSettingsMemberReady" in global_source
    assert "UserLlmSettingsCard" in global_source
    assert "GlobalLlmSettingsCard" in global_source


def test_ai_chat_gate_blocks_non_members_and_keeps_settings_notice_separate() -> None:
    ai_chat_source = AI_CHAT_PAGE.read_text(encoding="utf-8")

    assert "useMembershipSummary" in ai_chat_source
    assert "MemberOnlyFeatureNotice" in ai_chat_source
    assert "aiChatMemberBlocked" in ai_chat_source
    assert "interactionDisabled = !pid || !activeNodeId || !llmConfigured || aiChatMemberBlocked" in ai_chat_source
    assert "!aiChatMemberBlocked && !llmConfigured" in ai_chat_source


def test_membership_summary_refreshes_after_membership_mutations() -> None:
    source = MEMBERSHIP_QUERIES.read_text(encoding="utf-8")

    assert 'invalidateQueries({ queryKey: ["membership", "summary"] })' in source[source.index("useCreateMembershipOrder"):source.index("useInviteSummary")]


def test_member_only_gate_stays_out_of_project_settings() -> None:
    project_source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "MemberOnlyFeatureNotice" not in project_source
    assert "useMembershipSummary" not in project_source


def test_admin_membership_page_supports_manual_membership_grants() -> None:
    admin_api_source = ADMIN_API.read_text(encoding="utf-8")
    admin_queries_source = ADMIN_QUERIES.read_text(encoding="utf-8")
    admin_page_source = ADMIN_MEMBERSHIP_PAGE.read_text(encoding="utf-8")

    assert "AdminMembershipGrantSchema" in admin_api_source
    assert 'path: "/admin/membership/grants"' in admin_api_source
    assert "grantAdminMembershipMonths" in admin_api_source

    assert "useGrantAdminMembershipMonths" in admin_queries_source
    assert 'invalidateQueries({ queryKey: ["admin", "membership", "overview"] })' in admin_queries_source
    assert 'invalidateQueries({ queryKey: ["membership"] })' in admin_queries_source

    assert "grantMembershipUserId" in admin_page_source
    assert "grantMembershipMonths" in admin_page_source
    assert "useGrantAdminMembershipMonths" in admin_page_source
    assert "授予会员" in admin_page_source
    assert "授予月数" in admin_page_source


def test_membership_and_admin_api_schemas_expose_invite_discount_and_commission_fields() -> None:
    membership_api_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "membership.ts").read_text(encoding="utf-8")
    admin_api_source = ADMIN_API.read_text(encoding="utf-8")

    assert "discountCouponId" in membership_api_source
    assert "commissionAmountCent" in membership_api_source
    assert "pendingCommissionCent" in membership_api_source
    assert "withdrawableCommissionCent" in membership_api_source
    assert "couponType" in membership_api_source
    assert "discountRate" in membership_api_source
    assert "CommissionWithdrawalSchema" in membership_api_source
    assert "requestCommissionWithdrawal" in membership_api_source
    assert "listCommissionWithdrawals" in membership_api_source
    assert "PayoutIdentitySchema" in membership_api_source
    assert "getPayoutIdentity" in membership_api_source
    assert "startPayoutBindingAttempt" in membership_api_source
    assert "pollPayoutBindingAttempt" in membership_api_source
    assert "openMobilePayoutBinding" in membership_api_source
    assert "completePayoutBinding" in membership_api_source
    assert "qrCodePayload" in membership_api_source
    assert "mobileBindingUrl" in membership_api_source
    assert "confirmedLearningPyramidUserId" in membership_api_source
    assert "identityMaskedLabel" in membership_api_source
    assert "wechatOpenId" not in membership_api_source
    assert "processing" in membership_api_source
    assert "awaiting_confirmation" in membership_api_source
    assert "succeeded" in membership_api_source
    assert "failed" in membership_api_source

    assert "pendingCommissionCent" in admin_api_source
    assert "withdrawableCommissionCent" in admin_api_source
    assert "discountCouponId" in admin_api_source
    assert "commissionAmountCent" in admin_api_source
    assert "discountCoupon" in admin_api_source
    assert "AdminMembershipWithdrawalSchema" in admin_api_source
    assert "listAdminMembershipWithdrawals" in admin_api_source
    assert "resolveAdminMembershipWithdrawal" in admin_api_source
    assert "AdminPayoutIdentitySchema" in admin_api_source
    assert "listAdminPayoutIdentities" in admin_api_source
    assert "syncAdminMembershipWithdrawal" in admin_api_source
    assert "acknowledgeAdminWithdrawalWarning" in admin_api_source
    assert "identityMaskedLabel" in admin_api_source


def test_llm_settings_form_no_longer_wraps_fields_in_inner_capsule() -> None:
    llm_settings_source = LLM_SETTINGS_CARDS.read_text(encoding="utf-8")

    assert "theme-status-surface" not in llm_settings_source
    assert '<div className="space-y-3">' in llm_settings_source
    assert '<div className="grid gap-3">' in llm_settings_source


def test_llm_settings_card_uses_standard_header_divider() -> None:
    llm_settings_source = LLM_SETTINGS_CARDS.read_text(encoding="utf-8")

    assert '<CardHeader className="theme-card-header">' in llm_settings_source


def test_new_subject_creation_no_longer_applies_global_review_template() -> None:
    projects_source = PROJECTS_PAGE.read_text(encoding="utf-8")

    assert "useGlobalConfigStore" not in projects_source
    assert "defaultProjectReviewTemplate" not in projects_source
    assert "setLayerConfig(res.compatibilityProjectId, 0" not in projects_source
    assert "默认复习模板未自动套用" not in projects_source


def test_subject_project_contract_no_longer_exposes_compatibility_project_id() -> None:
    checked_sources = [
        SUBJECTS_API,
        APP_SHELL,
        PROJECTS_PAGE,
        SUBJECT_DASHBOARD_PAGE,
        PROJECT_SETTINGS_PAGE,
        REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx",
        REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroWorkbenchGate.tsx",
    ]

    for source_path in checked_sources:
        source = source_path.read_text(encoding="utf-8")
        assert "compatibilityProjectId" not in source

    subjects_api_source = SUBJECTS_API.read_text(encoding="utf-8")
    assert "subjectProjectId" not in subjects_api_source
    assert "projectId: z.string().nullable()" in subjects_api_source
    assert "const CreateSubjectResultSchema = z.object({" in subjects_api_source

    projects_source = PROJECTS_PAGE.read_text(encoding="utf-8")
    assert "subject.subjectProjectId" not in projects_source
    assert "res.subjectProjectId" not in projects_source

    subject_dashboard_source = SUBJECT_DASHBOARD_PAGE.read_text(encoding="utf-8")
    assert "subject?.subjectProjectId" not in subject_dashboard_source
    assert "material.projectId" in subject_dashboard_source

    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    assert "routeSubject?.subjectProjectId" not in app_shell_source
    assert "subjectContextQ.data?.currentMaterial.projectId" in app_shell_source


def test_global_theme_card_removes_legacy_location_description() -> None:
    global_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")
    section_start = global_source.index("<CardTitle>界面主题</CardTitle>")
    section_end = global_source.index("<CardContent", section_start)
    section = global_source[section_start:section_end]

    assert "原本右上角的主题选择已经迁到这里。番茄钟则已经独立成固定功能页。" not in global_source
    assert "<CardDescription" not in section
