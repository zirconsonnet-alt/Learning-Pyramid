from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SHELL = REPO_ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
MAIN_NAV = REPO_ROOT / "frontend" / "src" / "shell" / "MainNav.tsx"
NAV_ITEMS = REPO_ROOT / "frontend" / "src" / "shell" / "navItems.ts"


def test_header_project_dropdown_avoids_nested_capsule_surface() -> None:
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    main_nav_source = MAIN_NAV.read_text(encoding="utf-8")
    header_dropdown_source = app_shell_source[
        app_shell_source.index("function HeaderNavDropdown"):app_shell_source.index("function AccountMenuLink")
    ]

    assert '<div className="theme-soft-surface p-3">' not in header_dropdown_source
    assert 'rounded-2xl px-3 py-2.5' not in main_nav_source
    assert 'bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_hsl(var(--primary)/0.42)]' not in main_nav_source


def test_account_menu_avoids_nested_capsule_surface() -> None:
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    account_menu_helpers = app_shell_source[
        app_shell_source.index("function AccountMenuLink"):app_shell_source.index("export function AppShell")
    ]
    account_menu_render = app_shell_source[
        app_shell_source.index("{accountMenuOpen ? ("):app_shell_source.index('<main className="container relative z-10')
    ]

    assert '<div className="theme-soft-surface p-3">' not in account_menu_render
    assert 'rounded-2xl px-3 py-2.5' not in account_menu_helpers
    assert "[border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)]" not in account_menu_helpers
    assert 'rounded-xl px-2 py-2' in account_menu_helpers
    assert 'mt-4 border-t border-border/60 pt-3' in account_menu_render


def test_friends_center_lives_in_account_menu_not_global_nav() -> None:
    nav_source = NAV_ITEMS.read_text(encoding="utf-8")
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    account_menu_render = app_shell_source[
        app_shell_source.index("{accountMenuOpen ? ("):app_shell_source.index('<main className="container relative z-10')
    ]

    assert '{ to: "/friends", label: "好友中心", icon: UsersRound }' not in nav_source
    assert 'AccountMenuLink to="/friends" label="好友中心" icon={UsersRound}' in account_menu_render


def test_project_nav_places_ai_chat_above_recommended_review() -> None:
    nav_source = NAV_ITEMS.read_text(encoding="utf-8")
    project_nav_start = nav_source.index("export function getProjectNavItems")
    project_nav_source = nav_source[project_nav_start:]

    assert project_nav_source.index('label: "工作台"') < project_nav_source.index('label: "AI问答"')
    assert project_nav_source.index('label: "AI问答"') < project_nav_source.index('label: "推荐复习"')
    assert project_nav_source.index('label: "推荐复习"') < project_nav_source.index('label: "学习任务树"')
    assert "items.splice(4, 0, { to: `/p/${pid}/object-tree`, label: \"学习对象树\", icon: Workflow })" in project_nav_source
