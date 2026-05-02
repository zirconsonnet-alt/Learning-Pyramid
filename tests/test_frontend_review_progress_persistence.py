from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ReviewPane.tsx"
REVIEW_SESSION_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "reviewSessionStore.ts"


def test_review_pane_persists_in_progress_review_session_across_refresh() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "loadReviewSessionStateByHeadId(projectId)" in source
    assert "saveReviewSessionStateByHeadId(projectId, nextState)" in source
    assert "clearPersistedReviewSession(projectId, headId)" in source
    assert "answers: { ...current.answers, [rpId]: nextValue }" in source
    assert "activeRecallPointId: rpId" in source


def test_review_session_store_uses_project_scoped_local_storage_and_sanitizes_values() -> None:
    source = REVIEW_SESSION_STORE.read_text(encoding="utf-8")

    assert "plm-review-session:" in source
    assert "window.localStorage" in source
    assert "normalizeReviewSessionState" in source
    assert "value === 0 || value === 1" in source
    assert "loadReviewSessionStateByHeadId" in source
    assert "saveReviewSessionStateByHeadId" in source
    assert "clearPersistedReviewSession" in source
