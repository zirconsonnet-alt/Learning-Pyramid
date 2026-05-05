from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTH_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "auth" / "AuthPage.tsx"


def test_register_invite_copy_promotes_discount_coupon_without_optional_label() -> None:
    source = AUTH_PAGE.read_text(encoding="utf-8")

    assert "可选，填写后可绑定邀请关系" not in source
    assert "当前允许自由注册；如果填写邀请码，会额外绑定邀请关系。" not in source
    assert "绑定邀请码可获7.5折券" in source
