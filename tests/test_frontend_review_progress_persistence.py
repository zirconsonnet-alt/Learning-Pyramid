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
    assert "writtenAnswerDrafts" in source
    assert "submittedWrittenAnswers" in source
    assert "skippedWrittenAnswers" in source


def test_review_pane_requires_submitted_written_answer_before_reveal_or_judgement() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "提交答案" in source
    assert "hasSubmittedWrittenAnswer" in source
    assert "disabled={!hasSubmittedWrittenAnswer}" in source
    assert "先提交自己的答案，再查看答案或判断记忆状态。" in source


def test_review_pane_uses_rich_content_editor_for_written_answer_and_can_skip_to_forgotten() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "RichContentEditor" in source
    assert 'field="answer"' in source
    assert "appendImageBlock" in source
    assert "removeImageBlockAt" in source
    assert "richContentHasMeaning" in source
    assert "skipWrittenAnswer" in source
    assert "跳过" in source
    assert "answers: { ...current.answers, [rpId]: 0 }" in source
    assert "showAnswer: { ...current.showAnswer, [rpId]: true }" in source


def test_review_pane_reveals_answer_after_submitting_written_answer() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")
    submit_start = source.index("function submitWrittenAnswer")
    skip_start = source.index("function skipWrittenAnswer")
    submit_source = source[submit_start:skip_start]

    assert "submittedWrittenAnswers" in submit_source
    assert "showAnswer: { ...current.showAnswer, [rpId]: true }" in submit_source


def test_review_session_store_uses_project_scoped_local_storage_and_sanitizes_values() -> None:
    source = REVIEW_SESSION_STORE.read_text(encoding="utf-8")

    assert "plm-review-session:" in source
    assert "window.localStorage" in source
    assert "normalizeReviewSessionState" in source
    assert "value === 0 || value === 1" in source
    assert "writtenAnswerDrafts: normalizeRichContentMap(raw.writtenAnswerDrafts)" in source
    assert "submittedWrittenAnswers: normalizeRichContentMap(raw.submittedWrittenAnswers)" in source
    assert "skippedWrittenAnswers: normalizeBooleanMap(raw.skippedWrittenAnswers)" in source
    assert "loadReviewSessionStateByHeadId" in source
    assert "saveReviewSessionStateByHeadId" in source
    assert "clearPersistedReviewSession" in source
