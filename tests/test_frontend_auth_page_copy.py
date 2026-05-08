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
    assert "请到邮箱点击激活链接；验证完成后就能进入工作区。" in source
    assert "激活链接已重新发送" in source
    assert "你可以直接返回邮箱查收新邮件；如果还没收到，稍等几十秒后再试一次。" in source
    assert "等待邮箱验证" in source
