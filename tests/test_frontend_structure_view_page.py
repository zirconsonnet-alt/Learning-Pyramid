from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER = REPO_ROOT / "frontend" / "src" / "router.tsx"
NAV_ITEMS = REPO_ROOT / "frontend" / "src" / "shell" / "navItems.ts"
APP_SHELL = REPO_ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
STRUCTURE_VIEW_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "trees" / "StructureViewPage.tsx"
LEARNING_OBJECT_NODE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "learningObjects" / "LearningObjectNodePage.tsx"
LEARNING_TASK_NODE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "learningTasks" / "LearningTaskNodePage.tsx"
INSTANCE_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "instances" / "InstancePage.tsx"


def test_router_uses_single_structure_view_route() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert 'import { StructureViewPage } from "@/views/trees/StructureViewPage"' in source
    assert '{ path: "/p/:projectId/structure-view", element: lazyElement(<StructureViewPage />) }' in source
    assert "/p/:projectId/object-tree" not in source
    assert "/p/:projectId/task-tree" not in source


def test_structure_view_page_switches_between_object_and_task_tree() -> None:
    source = STRUCTURE_VIEW_PAGE.read_text(encoding="utf-8")

    assert 'type StructureViewMode = "object" | "task"' in source
    assert 'label="学习对象树"' in source
    assert 'label="学习任务树"' in source
    assert "LearningObjectTreePanel" in source
    assert "LearningTaskTreePanel" in source
    assert 'const requestedMode = searchParams.get("view")' in source
    assert 'setSearchParams(nextSearchParams, { replace: true })' in source


def test_project_header_titles_use_structure_view() -> None:
    source = APP_SHELL.read_text(encoding="utf-8")

    assert 'pathname.includes("/structure-view")' in source
    assert 'title: "结构视图"' in source
    assert 'title: "学习任务树"' not in source
    assert 'title: "学习对象树"' not in source


def test_detail_pages_return_to_structure_view() -> None:
    object_node_source = LEARNING_OBJECT_NODE_PAGE.read_text(encoding="utf-8")
    task_node_source = LEARNING_TASK_NODE_PAGE.read_text(encoding="utf-8")
    instance_source = INSTANCE_PAGE.read_text(encoding="utf-8")

    assert "/structure-view?view=object" in object_node_source
    assert "返回学习对象树" in object_node_source
    assert "/object-tree" not in object_node_source

    assert "/structure-view?view=task" in task_node_source
    assert "返回学习任务树" in task_node_source
    assert "/task-tree" not in task_node_source

    assert "/structure-view?view=object" in instance_source
    assert "返回学习对象树" in instance_source
    assert "/object-tree" not in instance_source
