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
    assert "chooseSessionAnswer" in source
    assert "本次复习" in source
    assert "已完成" in source
    assert "推荐指数" in source
    assert "记忆强度" in source


def test_review_recommendations_page_drops_read_only_list_copy() -> None:
    source = RECOMMENDATIONS_PAGE.read_text(encoding="utf-8")

    assert "这里只做只读复习浏览" not in source
    assert "当前是只读推荐复习批次" not in source
