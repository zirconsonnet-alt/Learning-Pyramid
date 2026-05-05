from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_TASK_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "reviewTasks" / "ReviewTaskPage.tsx"


def test_review_task_page_uses_learning_task_style_two_column_layout() -> None:
    source = REVIEW_TASK_PAGE.read_text(encoding="utf-8")

    assert "const summaryPanel = reviewTaskQ.data ? (" in source
    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "ReviewTaskSummaryCard" in source


def test_review_task_page_keeps_outcome_badges_in_result_list() -> None:
    source = REVIEW_TASK_PAGE.read_text(encoding="utf-8")

    assert 'title="复习结果详情"' in source
    assert "describeReviewOutcome(outcome)" in source
    assert "reviewOutcomeClasses(outcome)" in source
