from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTH_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "AuthPage.tsx"


def test_register_invite_copy_promotes_discount_coupon_without_optional_label() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert "可选，填写后可绑定邀请关系" not in source
    assert "当前允许自由注册；如果填写邀请码，会额外绑定邀请关系。" not in source
    assert "绑定邀请码可获7.5折券" in source


def test_verify_mode_renders_inline_email_delivery_state() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert "verifyEmailNotice" in source
    assert "验证邮件已发送" in source
    assert "请到邮箱点击激活链接；你可以在手机或电脑上完成验证，当前页面会自动继续。" in source
    assert "激活链接已重新发送" in source
    assert "如果这个邮箱已经注册且尚未验证，我们会重新发送激活链接；如果你刚清理过账号，请直接重新注册。" in source
    assert "等待邮箱验证" in source
    assert "重新注册" in source
    assert "nextParams.set(\"mode\", \"register\")" in source


def test_authenticated_verify_resend_page_redirects_to_workspace() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert 'currentUserQ.data && effectiveMode !== "reset" && (effectiveMode !== "verify" || !verifyTokenPresent)' in source


def test_verify_resend_request_returns_to_login_with_generic_feedback() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert 'showSuccessFeedback("验证邮件请求已处理", "如果账号尚未验证，我们会发送激活链接；如果已经完成验证，请直接登录。")' in source
    assert 'switchMode("login")' in source


def test_verify_wait_page_polls_cross_device_completion() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert "verificationWaitToken" in source
    assert "useEmailVerificationStatus" in source
    assert 'effectiveMode === "verify" && !verifyTokenPresent && Boolean(verificationWaitToken) ? "sent" : null' in source
    assert "verifyEmailNotice === \"sent\" && verificationWaitToken ? 2000 : false" in source
    assert "邮箱已验证，正在进入工作区。" in source
