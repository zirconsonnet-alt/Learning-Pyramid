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


def test_review_pane_requires_submitted_written_answer_before_judgement() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "提交答案" in source
    assert "hasSubmittedWrittenAnswer" in source
    assert "disabled={!hasSubmittedWrittenAnswer}" in source
    assert "先提交自己的答案或跳过，再判断记忆状态。" not in source


def test_review_pane_anchor_label_links_to_instance_detail() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "formatAnchorLabel(" in source
    assert 'to={`/p/${projectId}/instances/${activeAnchor.instanceId}`}' in source
    assert "打开视频实例详情" in source
    assert "onOpenAnchor(activeAnchor)" in source


def test_review_pane_uses_rich_content_editor_for_written_answer_and_can_skip_to_reveal_answer() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")
    skip_start = source.index("function skipWrittenAnswer")
    insight_start = source.index("function toggleInsightEditor")
    skip_source = source[skip_start:insight_start]

    assert "RichContentEditor" in source
    assert 'field="answer"' in source
    assert "appendImageBlock" in source
    assert "removeImageBlockAt" in source
    assert "richContentHasMeaning" in source
    assert "skipWrittenAnswer" in skip_source
    assert "跳过" in source
    assert "answers: { ...current.answers, [rpId]: 0 }" not in skip_source
    assert "showAnswer: { ...current.showAnswer, [rpId]: true }" in skip_source
    assert "skippedWrittenAnswers" in skip_source


def test_review_pane_removes_manual_answer_visibility_button() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")

    assert "toggleAnswerVisibility" not in source
    assert "查看答案" not in source
    assert "收起答案" not in source


def test_review_pane_reveals_answer_after_submitting_written_answer() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")
    submit_start = source.index("function submitWrittenAnswer")
    skip_start = source.index("function skipWrittenAnswer")
    submit_source = source[submit_start:skip_start]

    assert "submittedWrittenAnswers" in submit_source
    assert "showAnswer: { ...current.showAnswer, [rpId]: true }" in submit_source


def test_review_pane_uses_single_layer_insight_editor_prompt() -> None:
    source = REVIEW_PANE.read_text(encoding="utf-8")
    placeholder = 'placeholder="补充这道复习点的新理解、易错点、联想线索或自己的话解释。"'
    placeholder_start = source.index(placeholder)
    insight_source = source[placeholder_start - 300 : placeholder_start + 500]

    assert placeholder in insight_source
    assert "rounded-2xl border" not in insight_source
    assert "提交本轮复习时，这段内容会作为新的" not in insight_source


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
