from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRIENDS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "friends" / "FriendsPage.tsx"
NAV_ITEMS = REPO_ROOT / "frontend" / "src" / "shell" / "navItems.ts"


def test_friends_page_trims_redundant_intro_copy_and_jump_button() -> None:
    source = FRIENDS_PAGE.read_text(encoding="utf-8")

    assert "好友中心" in source
    assert "好友学习排行榜" in source
    assert "发送申请、处理申请和查看好友资料都在这里，保留最常用的入口就够了。" not in source
    assert "按有效学习时长排序，同分时参考学习动作、活跃天数和最近学习时间。" not in source
    assert "onShowLeaderboard" not in source
    assert "leaderboardRef" not in source
    assert "leaderboardPulse" not in source


def test_global_nav_uses_friend_center_label() -> None:
    source = NAV_ITEMS.read_text(encoding="utf-8")

    assert '{ to: "/friends", label: "好友中心", icon: UsersRound }' in source
    assert '{ to: "/friends", label: "好友", icon: UsersRound }' not in source
