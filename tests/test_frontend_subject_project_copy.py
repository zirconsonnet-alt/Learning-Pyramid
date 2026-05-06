from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "projects" / "ProjectsPage.tsx"
SUBJECT_DASHBOARD_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "subjects" / "SubjectDashboardPage.tsx"
STUDY_MATERIALS = REPO_ROOT / "frontend" / "src" / "ui" / "subjects" / "studyMaterials.ts"


def test_subject_cards_show_project_count_before_last_study() -> None:
    source = PROJECTS_PAGE.read_text(encoding="utf-8")
    card_description = source[source.index("<CardDescription"):source.index("</CardDescription>", source.index("<CardDescription"))]

    assert "listSubjectMaterials" in source
    assert "subjectMaterialCountBySubjectId" in source
    assert "{subjectProjectCountText}" in card_description
    assert card_description.index("{subjectProjectCountText}") < card_description.index("lastStudyDisplay.text")


def test_create_subject_dialog_and_new_project_card_remove_helper_copy() -> None:
    projects_source = PROJECTS_PAGE.read_text(encoding="utf-8")
    dashboard_source = SUBJECT_DASHBOARD_PAGE.read_text(encoding="utf-8")

    assert "学科是复习、复述点、层推进和统计的共享空间" not in projects_source
    assert "当前版本会先创建一个默认项目" not in projects_source
    assert "像学科中心一样，从这里新建网课、书本或零散知识点项目。" not in dashboard_source


def test_book_project_creation_hint_uses_short_activity_copy() -> None:
    source = STUDY_MATERIALS.read_text(encoding="utf-8")

    assert 'return "适合看书记笔记，做题"' in source
    assert "创建后会直接进入项目设置" not in source


def test_subject_project_pages_avoid_compatibility_project_wording() -> None:
    for source_path in (PROJECTS_PAGE, SUBJECT_DASHBOARD_PAGE, STUDY_MATERIALS):
        source = source_path.read_text(encoding="utf-8")
        assert "compatibilityProjectId" not in source
        assert "兼容项目" not in source
        assert "兼容工作台" not in source
        assert "兼容入口" not in source
