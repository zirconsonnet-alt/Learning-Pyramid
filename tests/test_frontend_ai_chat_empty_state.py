from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"


def test_unselected_ai_chat_context_uses_rich_empty_state() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "先选择一个节点开始提问" in source
    assert "请从左侧选择一个学习任务节点或学习对象节点" in source
    assert "mx-auto flex max-w-3xl flex-col items-center px-2 pt-16 text-center" in source
    assert "请从左侧选择一个节点</div>" not in source
