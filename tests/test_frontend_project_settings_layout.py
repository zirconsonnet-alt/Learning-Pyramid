from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "ProjectSettingsPage.tsx"


def test_project_settings_moves_type_and_directory_status_into_header_rows() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "当前项目类型：" not in source
    assert "const subjectSummary =" in source
    assert "const directorySummary =" in source
    assert '<span className="theme-pill-default inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">' in source
    assert "本地素材目录 ·" in source


def test_project_settings_removes_rollup_and_layer_helper_notices() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "当前项目使用“{getRollUpStrategyLabel(rollUpStrategy)}”。{getRollUpStrategyDescription(rollUpStrategy)}" not in source
    assert "下面的阈值参数会继续保存，但只有切回“阈值自动上推”时才会参与自动推进。" not in source


def test_project_settings_renders_layer_config_as_peer_card() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "layerConfigSection" not in source
    assert "<LayerConfigEditor" in source
    assert "embedded" not in source[source.index("<LayerConfigEditor"):source.index("/>", source.index("<LayerConfigEditor"))]
