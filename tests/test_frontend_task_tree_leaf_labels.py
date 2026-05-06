from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_TREE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "TaskTreePage.tsx"
TASK_TREE_CANVAS = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "components" / "LearningTaskTreeCanvas.tsx"
OBJECT_TREE_CANVAS = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "components" / "LearningObjectTreeCanvas.tsx"
TREE_VIEWPORT = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "components" / "TreeCanvasViewport.tsx"
AI_CHAT_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"
LEARNING_TASK_NODE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "learningTasks" / "LearningTaskNodePage.tsx"


def test_task_tree_leaf_nodes_do_not_render_leaf_label() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    canvas_source = TASK_TREE_CANVAS.read_text(encoding="utf-8")

    assert "叶子任务" not in page_source
    assert "叶子任务" not in canvas_source
    assert ': undefined,' in page_source
    assert "metaText ? <div" in canvas_source


def test_task_tree_uses_registered_target_layer_without_object_mirror_semantics() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    api_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "learningTaskNodes.ts").read_text(encoding="utf-8")

    assert "targetLayerIndex: z.number().int().nullable().optional().default(null)" in api_source
    assert "if (node.targetLayerIndex !== null) layerById[node.nodeId] = node.targetLayerIndex" in page_source
    assert "OBJECT_MIRROR" not in page_source
    assert "boundLearningObjectNodeId" not in api_source
    assert "objectMirrorStatus" not in api_source
    assert 'return "chapter"' in page_source


def test_task_tree_uses_only_real_children_for_edges() -> None:
    page_source = TASK_TREE_PAGE.read_text(encoding="utf-8")
    api_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "learningTaskNodes.ts").read_text(encoding="utf-8")

    assert "getTaskTreeChildIds(node)" in page_source
    assert "displayChildNodeIds" not in api_source
    assert "displayChildNodeIds" not in page_source
    assert "return node.children" in page_source


def test_ai_chat_task_sidebar_uses_only_real_children_for_edges() -> None:
    page_source = AI_CHAT_PAGE.read_text(encoding="utf-8")

    assert "getTaskSidebarChildIds(node)" in page_source
    assert "displayChildNodeIds" not in page_source
    assert "return node.children" in page_source
    assert "displayParentById[childId] = node.nodeId" in page_source
    assert "displayParentById[node.nodeId] ?? node.parentId" in page_source


def test_learning_task_node_detail_uses_real_children_count_and_no_helper_copy() -> None:
    page_source = LEARNING_TASK_NODE_PAGE.read_text(encoding="utf-8")

    assert "getLearningTaskNodeDisplayChildIds(nodeQ.data)" in page_source
    assert "displayChildNodeIds" not in page_source
    assert "return node.children" in page_source
    assert "nodeQ.data.children.length" not in page_source
    assert "先确认这个聚合节点覆盖的规模，再继续查看下方的复述点。" not in page_source


def test_tree_canvases_offer_zoom_and_wider_layout_spacing() -> None:
    task_canvas_source = TASK_TREE_CANVAS.read_text(encoding="utf-8")
    object_canvas_source = OBJECT_TREE_CANVAS.read_text(encoding="utf-8")
    viewport_source = TREE_VIEWPORT.read_text(encoding="utf-8")

    assert 'aria-label="缩放树图"' in viewport_source
    assert "zoomPercent" in viewport_source
    assert "transform: `scale(${zoom})`" in viewport_source
    assert "const COLUMN_WIDTH = 240" in task_canvas_source
    assert "const COLUMN_WIDTH = 240" in object_canvas_source
    assert "const SIBLING_GAP = 28" in task_canvas_source
    assert "const SIBLING_GAP = 28" in object_canvas_source
    assert "const branchY = startY + 26" in task_canvas_source
    assert "const branchY = startY + 26" in object_canvas_source
