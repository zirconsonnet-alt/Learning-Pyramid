from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "GlobalSettingsPage.tsx"
PROJECT_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "ProjectSettingsPage.tsx"
AI_CHAT_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"


def test_llm_settings_live_in_global_settings_below_access_center() -> None:
    global_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "useMyLlmSettings" in global_source
    assert "useGlobalLlmSettings" in global_source
    assert "大模型配置" in global_source
    assert global_source.index("<CardTitle>系统接入中心</CardTitle>") < global_source.index("大模型配置")


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
