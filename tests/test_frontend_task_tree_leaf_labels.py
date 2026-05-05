from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_TREE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "TaskTreePage.tsx"
TASK_TREE_CANVAS = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "components" / "LearningTaskTreeCanvas.tsx"
AI_CHAT_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"


def test_task_tree_leaf_nodes_do_not_render_leaf_label() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    canvas_source = TASK_TREE_CANVAS.read_text(encoding="utf-8")

    assert "叶子任务" not in page_source
    assert "叶子任务" not in canvas_source
    assert ': undefined,' in page_source
    assert "metaText ? <div" in canvas_source


def test_task_tree_uses_registered_target_layer_for_object_mirrors() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    api_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "learningTaskNodes.ts").read_text(encoding="utf-8")

    assert "targetLayerIndex: z.number().int().nullable().optional().default(null)" in api_source
    assert "if (node.targetLayerIndex !== null) layerById[node.nodeId] = node.targetLayerIndex" in page_source
    assert 'node.nodeOrigin === "OBJECT_MIRROR"' in page_source
    assert 'return "chapter"' in page_source


def test_task_tree_uses_display_children_for_object_mirror_edges() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    api_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "learningTaskNodes.ts").read_text(encoding="utf-8")

    assert "displayChildNodeIds: z.array(z.string()).nullable().optional().default(null)" in api_source
    assert "getTaskTreeChildIds(node)" in page_source
    assert "node.displayChildNodeIds ?? node.children" in page_source


def test_ai_chat_task_sidebar_uses_display_children_for_object_mirror_edges() -> None:
    page_source = AI_CHAT_PAGE.read_text(encoding="utf-8")

    assert "getTaskSidebarChildIds(node)" in page_source
    assert "node.displayChildNodeIds ?? node.children" in page_source
    assert "displayParentById[childId] = node.nodeId" in page_source
    assert "displayParentById[node.nodeId] ?? node.parentId" in page_source
