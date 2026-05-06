from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "convergences" / "ConvergencePage.tsx"


def test_convergence_page_uses_read_only_detail_layout() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const summaryPanel = convergenceQ.data ? (" in source
    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "ConvergenceSummaryCard" in source
    assert "ConvergenceRoundListCard" in source
    assert "复习轮次" in source
    assert "查看复习任务" in source
    assert "ConvergenceReviewWorkspaceCard" not in source
    assert "复习工作区" not in source
    assert "ChevronLeft" in source
    assert "RefreshCw" in source


def test_convergence_page_does_not_embed_review_execution_workspace() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "RichContentRenderer" not in source
    assert "activeRecallPointId" not in source
    assert "revealedAnswerIds" not in source
    assert "显示答案" not in source
    assert "复习判断" not in source
    assert "记得" not in source
    assert "不记得" not in source
