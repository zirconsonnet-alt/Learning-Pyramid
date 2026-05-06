from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "convergences" / "ConvergencePage.tsx"


def test_convergence_page_uses_review_detail_layout() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const summaryPanel = convergenceQ.data ? (" in source
    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "ConvergenceSummaryCard" in source
    assert "ConvergenceReviewWorkspaceCard" in source
    assert "复习工作区" in source
    assert "ChevronLeft" in source
    assert "RefreshCw" in source


def test_convergence_page_copies_workbench_review_workspace_ui() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "activeEntry" in source
    assert "显示答案" in source
    assert "复习判断" in source
    assert "记得" in source
    assert "不记得" in source
    assert "打开复述点详情" in source
    assert "ReviewTaskSummaryCard" not in source
