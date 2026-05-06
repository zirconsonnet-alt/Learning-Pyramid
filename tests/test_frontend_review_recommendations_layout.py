from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATIONS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "recommendations" / "ReviewRecommendationsPage.tsx"


def test_review_recommendations_page_updates_unanswered_entries_by_threshold() -> None:
    source = RECOMMENDATIONS_PAGE.read_text(encoding="utf-8")

    assert "useAllReviewRecommendations" in source
    assert "thresholdDialogOpen" in source
    assert "recommendationThresholdPercent" in source
    assert "thresholdDraft" in source
    assert "更新推荐阈值" in source
    assert "answeredRecallPointIds" in source
    assert "estimatedMemoryStrength < threshold" in source
    assert "按阈值更新后，只会替换还没答过的复述点" in source


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
    assert "从系统推荐开始，也可以搜索复述点加入这次复习。" not in source
    assert "复述点搜索" not in source
    assert "本次复习" not in source
    assert "刷新推荐" not in source
    assert "上一批" not in source
    assert "继续推荐" not in source
