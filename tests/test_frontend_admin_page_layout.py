from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "admin" / "AdminPage.tsx"
ADMIN_NAV = REPO_ROOT / "frontend" / "src" / "views" / "admin" / "AdminNav.tsx"


def test_admin_overview_is_current_operations_console_not_legacy_user_list() -> None:
    source = ADMIN_PAGE.read_text(encoding="utf-8")

    assert "运营控制台" in source
    assert "风险巡检" in source
    assert "平台治理" in source
    assert "会员运营" in source
    assert "数据安全状态" in source
    assert "useAdminUsers" not in source
    assert "admin-user-search" not in source
    assert "旧社区入口已收口" not in source
    assert "后台说明" not in source


def test_admin_navigation_uses_icon_tabs_for_current_admin_surfaces() -> None:
    source = ADMIN_NAV.read_text(encoding="utf-8")

    assert "LayoutDashboard" in source
    assert "CreditCard" in source
    assert "UsersRound" in source
    assert 'aria-label={`进入${item.label}`}' in source
