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


def test_project_settings_layer_config_avoids_nested_capsule_sections() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")
    layer_editor_source = source[source.index("function LayerConfigEditor"):]

    assert 'className="grid gap-4 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4 md:grid-cols-2"' not in layer_editor_source
    assert 'className="space-y-3 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4"' not in layer_editor_source
    assert '<div className="border-t border-border/60" />' in layer_editor_source
    assert '<section className="space-y-3">' in layer_editor_source


def test_project_settings_danger_zone_uses_dialog_confirmation() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "function DangerZoneCard" not in source
    assert 'id="danger-zone-confirmation"' not in source
    assert "<DangerZoneCard" not in source


def test_project_settings_keeps_delete_button_for_default_project_scope() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "showDangerZone" not in source
    assert "<DangerZoneCard" not in source
    assert "const showDangerZone = deleteActionRemovesSubject || canDeleteCurrentMaterial" not in source
    assert 'actionLabel={deleteActionRemovesSubject ? "删除学科" : "删除当前项目"}' not in source
    assert 'confirmationLabel={deleteActionRemovesSubject ? "输入学科标题以确认删除" : "输入项目名称以确认删除"}' not in source


def test_project_settings_uses_clean_subject_project_copy_and_project_id() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "兼容入口" not in source
    assert "兼容工作台" not in source
    assert "compatibilityProjectId" not in source
    assert "material.projectId" in source
    assert "删除项目只会移除" not in source


def test_project_settings_top_level_headers_use_divider_style() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert '<CardHeader className="theme-card-header border-b border-[color:var(--theme-soft-border)] pb-6">' in source
    assert '<CardHeader className="space-y-4 border-b border-[color:var(--theme-soft-border)] pb-6">{header}</CardHeader>' in source


def test_project_and_subject_settings_headers_use_icon_title_pattern() -> None:
    source = PROJECT_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "function SettingsCardTitle" in source
    assert '<div className="theme-icon-surface h-11 w-11 shrink-0">' in source
    assert '<SettingsCardTitle icon={FolderTree} title="学科信息" />' in source
    assert '<SettingsCardTitle icon={Settings2} title="基本信息" />' in source
    assert '<SettingsCardTitle icon={Boxes} title="层配置" />' in source
