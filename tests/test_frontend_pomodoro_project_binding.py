from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SHELL = ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
POMODORO_TRANSITION_EFFECT = ROOT / "frontend" / "src" / "shell" / "PomodoroTransitionEffect.tsx"
POMODORO_PAGE = ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx"
POMODORO_GATE = ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroWorkbenchGate.tsx"
POMODORO_DOC = ROOT / "docs" / "how-to-use-pomodoro.md"
USER_MANUAL = ROOT / "docs" / "learningpyramid-user-manual.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quick_pomodoro_ignores_subject_root_and_stale_selected_project() -> None:
    source = read(POMODORO_PAGE)

    assert "subjectRootProjectIds" in source
    assert "selectedWorkbenchProjectId" in source
    assert "material.projectId !== subject.subjectProjectId" in source
    assert "projectTitleMap.has(selectedProjectId)" in source
    assert "!subjectRootProjectIds.has(selectedProjectId)" in source
    assert "pomodoroProjectCatalogReady" in source
    assert "startQuickPomodoro(selectedWorkbenchProjectId || null)" in source
    assert "const fallbackWorkbenchPath = selectedWorkbenchProjectId ? `/p/${selectedWorkbenchProjectId}/workbench` : \"\"" in source
    assert "selectedWorkbenchProjectId" in source[source.index("const preferredWorkbenchLabel ="):]


def test_pomodoro_workbench_lock_excludes_subject_root_projects() -> None:
    app_shell = read(APP_SHELL)
    gate = read(POMODORO_GATE)

    assert "const subjectsQ = useSubjects(canAccessApp)" in app_shell
    assert "subjectRootProjectIds" in app_shell
    assert "pomodoroProjectCatalogReady" in app_shell
    assert ".filter((project) => !subjectRootProjectIds.has(project.projectId))" in app_shell
    assert "useSubjects(true)" in gate
    assert "subjectRootProjectIds" in gate
    assert "pomodoroProjectCatalogReady" in gate
    assert ".filter((item) => !subjectRootProjectIds.has(item.projectId))" in gate


def test_pomodoro_transition_only_claims_binding_for_resolved_project_title() -> None:
    source = read(POMODORO_TRANSITION_EFFECT)

    assert "hasProjectBinding: Boolean(currentProjectTitle)" in source
    assert "hasProjectBinding: Boolean(snapshot.currentProjectId)" not in source


def test_pomodoro_docs_explain_concrete_project_binding_for_quick_pomodoro() -> None:
    pomodoro_doc = read(POMODORO_DOC)
    user_manual = read(USER_MANUAL)

    assert "先选择学科，再为每个番茄绑定该学科下要学习的具体项目" in pomodoro_doc
    assert "只有当前选中的是学科下的具体项目时，系统才会把这次小番茄绑定到该项目" in pomodoro_doc
    assert "学科入口或旧的不可用项目" in pomodoro_doc
    assert "学科入口本身不会作为番茄绑定目标" in user_manual
    assert "若当前停留在学科入口或旧的不可用项目上，小番茄会按未绑定项目计时" in user_manual
