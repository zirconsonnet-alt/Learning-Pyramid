from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"
TASK_NODE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "learningTasks" / "LearningTaskNodePage.tsx"


def test_unselected_ai_chat_context_uses_rich_empty_state() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "先选择一个节点开始提问" in source
    assert "请从左侧选择一个学习任务节点或学习对象节点" in source
    assert "mx-auto flex max-w-3xl flex-col items-center px-2 pt-16 text-center" in source
    assert "请从左侧选择一个节点</div>" not in source


def test_unselected_ai_chat_defaults_to_learning_object_tree_without_ui_copy_change() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'const defaultAiChatContextKind: AiChatContextKind = "object"' in source
    assert 'const fallbackKind: AiChatContextKind = kindParam === "recall" ? "recall" : defaultAiChatContextKind' in source
    assert 'queryKey: ["learningObjectNodes", pid]' in source
    assert "listLearningTaskNodes" not in source
    assert "listRecallPointsByLearningTaskNode" not in source
    assert "learningTaskNodeId:" not in source
    assert 'title="学习任务节点"' in source
    assert 'icon="task"' in source
    assert 'conversation.contextKind !== "task"' in source


def test_learning_task_detail_ai_button_does_not_open_task_tree_context() -> None:
    source = TASK_NODE_PAGE.read_text(encoding="utf-8")

    assert 'buildAiChatPath(pid, { kind: "task", nodeId: nid })' not in source
    assert 'to={`/p/${pid}/ai-chat`}' in source
