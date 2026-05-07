from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SHELL = REPO_ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
MAIN_NAV = REPO_ROOT / "frontend" / "src" / "shell" / "MainNav.tsx"


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
