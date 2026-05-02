from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ComposePane.tsx"


def test_compose_pane_moves_references_into_answer_area() -> None:
    source = COMPOSE_PANE.read_text(encoding="utf-8")

    assert "引用关系" not in source
    assert "答案引用" in source
    assert "selected-reference-link" in source
    assert "removeDraftReference(projectId, activeDraft.localId, referenceId)" in source


def test_course_anchor_is_readable_editable_and_normalized_for_submit() -> None:
    source = COMPOSE_PANE.read_text(encoding="utf-8")

    assert "function formatCourseAnchorPositionForInput" in source
    assert "function normalizeCourseAnchorPositionForSubmit" in source
    assert "disabled={usesResolvableCourseAnchor}" not in source
    assert "normalizeAnchorPositionForSubmit(d.position" in source
