import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "GlobalSettingsPage.tsx"
PROJECT_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "ProjectSettingsPage.tsx"


def assert_settings_pills_use_theme_tokens(source: str) -> None:
    fixed_palette_class = re.compile(
        r"\b(?:border|bg|text|focus-visible:ring)-"
        r"(?:emerald|amber|rose|slate|sky|blue|purple|violet|indigo|cyan|teal|green|yellow|orange|red|pink|gray|zinc|stone)-"
    )

    lines_to_check = [
        line
        for line in source.splitlines()
        if "rounded-full" in line or re.search(r'return ".*(?:border|bg|text)-', line)
    ]
    checked_source = "\n".join(lines_to_check)

    assert not fixed_palette_class.search(checked_source)
    assert "border-[#" not in checked_source
    assert "bg-[#" not in checked_source
    assert "text-[#" not in checked_source
    assert "focus-visible:ring-[#" not in checked_source
    assert "theme-pill-accent" in source
    assert "theme-pill-warm" in source
    assert "theme-pill-danger" in source


def test_global_settings_pills_use_theme_tokens_instead_of_fixed_palettes() -> None:
    source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    fixed_palette_class = re.compile(
        r"\b(?:border|bg|text|focus-visible:ring)-"
        r"(?:emerald|amber|rose|slate|sky|blue|purple|violet|indigo|cyan|teal|green|yellow|orange|red|pink|gray|zinc|stone)-"
    )
    lines_to_check = [
        line
        for line in source.splitlines()
        if "rounded-full" in line or re.search(r'return ".*(?:border|bg|text)-', line)
    ]
    checked_source = "\n".join(lines_to_check)

    assert not fixed_palette_class.search(checked_source)
    assert "border-[#" not in checked_source
    assert "bg-[#" not in checked_source
    assert "text-[#" not in checked_source
    assert "focus-visible:ring-[#" not in checked_source


def test_global_settings_layout_keeps_access_modules_out_of_theme_only_page() -> None:
    source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "<CardTitle>全局配置</CardTitle>" not in source
    assert "<CardTitle>番茄钟入口</CardTitle>" not in source
    assert "<CardTitle>系统接入中心</CardTitle>" not in source
    assert "这类接入属于全局能力" not in source
    assert "云盘授权不属于个人资料展示" not in source
    assert "百度网盘" not in source
    assert "接入模块" not in source
    assert "只作用于未来新项目" not in source
    assert "当前模板摘要" not in source
    assert "休息音乐目录" not in source


def test_project_settings_pills_use_theme_tokens_instead_of_fixed_palettes() -> None:
    assert_settings_pills_use_theme_tokens(PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8"))
