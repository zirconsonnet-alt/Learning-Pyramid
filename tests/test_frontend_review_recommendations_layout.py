from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATIONS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "recommendations" / "ReviewRecommendationsPage.tsx"


def test_review_recommendations_page_can_search_and_add_recall_points() -> None:
    source = RECOMMENDATIONS_PAGE.read_text(encoding="utf-8")

    assert "searchRecallPoints" in source
    assert "deferredRecallPointSearchQuery" in source
    assert "manualReviewRecallPoints" in source
    assert "复述点搜索" in source
    assert "加入复习" in source


def test_review_recommendations_page_uses_workbench_style_review_and_stats() -> None:
    source = RECOMMENDATIONS_PAGE.read_text(encoding="utf-8")

    assert "reviewWorkspaceEntries" in source
    assert "ClipboardCheck" in source
    assert "theme-progress-track" in source
    assert "第 {activeReviewEntryIndex + 1} 题" in source
    assert "你的答案" in source
    assert "提交答案" in source
    assert "跳过" in source
    assert "记得" in source
    assert "不记得" in source
    assert "回答后自动切到下一题" in source


def test_review_recommendations_page_drops_read_only_list_copy() -> None:
    source = RECOMMENDATIONS_PAGE.read_text(encoding="utf-8")

    assert "这里只做只读复习浏览" not in source
    assert "当前是只读推荐复习批次" not in source
