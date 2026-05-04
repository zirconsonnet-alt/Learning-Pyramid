import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
GUIDE_PAGE = SRC / "views" / "guide" / "GuidePage.tsx"
PROJECTS_PAGE = SRC / "views" / "projects" / "ProjectsPage.tsx"
SUBJECT_DASHBOARD_PAGE = SRC / "views" / "subjects" / "SubjectDashboardPage.tsx"
PROJECT_SETTINGS_PAGE = SRC / "views" / "settings" / "ProjectSettingsPage.tsx"
LEARNING_OBJECT_TREE = SRC / "views" / "workbench" / "components" / "LearningObjectTree.tsx"
COMPOSE_PANE = SRC / "views" / "workbench" / "components" / "ComposePane.tsx"
REVIEW_PANE = SRC / "views" / "workbench" / "components" / "ReviewPane.tsx"
APP_SHELL = SRC / "shell" / "AppShell.tsx"
NAV_ITEMS = SRC / "shell" / "navItems.ts"
MAIN_NAV = SRC / "shell" / "MainNav.tsx"
WALKTHROUGH_DIR = SRC / "ui" / "guideWalkthrough"
COPY_MODULE = WALKTHROUGH_DIR / "guideWalkthroughCopy.ts"
STEPS_MODULE = WALKTHROUGH_DIR / "guideWalkthroughSteps.ts"
CONTROLLER_MODULE = WALKTHROUGH_DIR / "guideWalkthroughController.ts"
CREATE_SUBJECT_PROJECT_DOC = ROOT / "docs" / "how-to-create-subject-project.md"
STUDY_REVIEW_DOC = ROOT / "docs" / "how-to-study-review.md"
GUIDE_DOCUMENTS = {
    "create-subject-project": CREATE_SUBJECT_PROJECT_DOC,
    "study-review": STUDY_REVIEW_DOC,
}
CONTRACT_STEP_MAP = ROOT / "specs" / "003-driver-page-guide" / "contracts" / "walkthrough-step-map.md"


FIRST_RELEASE_STEP_IDS = [
    "create-subject",
    "create-subject-submit",
    "choose-project",
    "authorize-directory",
    "import-directory",
    "select-learning-object",
    "add-recall-point",
    "fill-recall-question",
    "fill-recall-answer",
    "submit-learning",
    "submit-review-answer",
    "mark-review-result",
    "submit-review",
]

FIRST_RELEASE_ANCHORS = [
    "new-subject-button",
    "create-subject-submit",
    "subject-project-settings-entry",
    "authorize-directory-button",
    "import-directory-button",
    "learning-object-tree-item",
    "add-recall-point-button",
    "recall-question-editor",
    "recall-answer-editor",
    "submit-learning-button",
    "submit-review-answer-button",
    "review-memory-choice-buttons",
    "submit-review-button",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def frontend_sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SRC.rglob("*") if path.suffix in {".ts", ".tsx"})


def has_anchor_coverage(source: str, anchor: str) -> bool:
    return f'data-guide-tour="{anchor}"' in source or f'guideTourAnchor: "{anchor}"' in source


def parse_document_sections(path: Path) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in read(path).splitlines():
        match = re.match(r"^##\s+(.+)$", line)
        if match:
            current_heading = match.group(1).strip()
            sections[current_heading] = []
            continue
        if current_heading:
            sections[current_heading].append(line)
    return {heading: "\n".join(lines) for heading, lines in sections.items()}


def ordered_items(section: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^\d+\.\s+(.+)$", section, flags=re.MULTILINE)]


def parse_steps() -> list[dict[str, object]]:
    source = read(STEPS_MODULE)
    steps: list[dict[str, object]] = []
    for block in re.findall(r"\{\s*id:\s*\"[^\"]+\".*?popoverSide:\s*\"[^\"]+\",\s*\}", source, flags=re.DOTALL):
        step_id = re.search(r"id:\s*\"([^\"]+)\"", block)
        heading = re.search(r"heading:\s*\"([^\"]+)\"", block)
        item_index = re.search(r"itemIndex:\s*(\d+)", block)
        item_indexes = re.search(r"itemIndexes:\s*\[([^\]]+)\]", block)
        target_anchor = re.search(r"targetAnchor:\s*\"([^\"]+)\"", block)
        fallback_mode = re.search(r"fallbackMode:\s*\"([^\"]+)\"", block)
        if not step_id:
            continue
        steps.append(
            {
                "id": step_id.group(1),
                "heading": heading.group(1) if heading else "",
                "itemIndex": int(item_index.group(1)) if item_index else None,
                "itemIndexes": [int(value) for value in re.findall(r"\d+", item_indexes.group(1))] if item_indexes else [],
                "targetAnchor": target_anchor.group(1) if target_anchor else "",
                "fallbackMode": fallback_mode.group(1) if fallback_mode else "",
            }
        )
    return steps


def test_driver_dependency_is_declared():
    package_json = json.loads(read(FRONTEND / "package.json"))
    assert "driver.js" in package_json.get("dependencies", {})

    lock = read(FRONTEND / "pnpm-lock.yaml")
    assert "driver.js" in lock


def test_walkthrough_modules_exist_with_contract_exports():
    assert COPY_MODULE.exists()
    assert STEPS_MODULE.exists()
    assert CONTROLLER_MODULE.exists()

    steps = read(STEPS_MODULE)
    assert "export type GuideWalkthroughStep" in steps
    for field in ["id", "sourceRef", "routeHint", "targetAnchor", "fallbackMode", "popoverSide"]:
        assert field in steps
    assert "export type GuideWalkthroughSessionStatus" in steps

    controller = read(CONTROLLER_MODULE)
    for symbol in [
        "startGuideWalkthrough",
        "destroyGuideWalkthrough",
        "refreshGuideWalkthrough",
        "useGuideWalkthroughController",
        "cleanupGuideWalkthrough",
    ]:
        assert symbol in controller


def test_app_shell_mounts_walkthrough_controller_and_css():
    app_shell = read(APP_SHELL)
    assert 'driver.js/dist/driver.css' in app_shell
    assert "useGuideWalkthroughController" in app_shell


def test_copy_module_exports_task_document_source_constants():
    copy_source = read(COPY_MODULE)
    assert "docs/how-to-create-subject-project.md" in copy_source
    assert "docs/how-to-study-review.md" in copy_source
    assert "guideWalkthroughCopySources" in copy_source
    assert "resolveGuideWalkthroughCopy" in copy_source


def test_guide_page_replaces_manual_with_two_task_documents():
    guide_page = read(GUIDE_PAGE)
    assert "plm-method-guide.md?raw" not in guide_page
    assert "learningpyramid-user-manual.md?raw" not in guide_page
    assert 'label: "系统使用说明"' not in guide_page
    assert 'slug: "manual"' not in guide_page
    assert 'slug: "create-subject-project"' in guide_page
    assert 'label: "如何创建学科项目"' in guide_page
    assert 'slug: "study-review"' in guide_page
    assert 'label: "如何学习复习"' in guide_page
    assert "createSubjectProjectMarkdown" in guide_page
    assert "studyReviewMarkdown" in guide_page


def test_guide_page_renders_start_action_wired_to_walkthrough_api():
    guide_page = read(GUIDE_PAGE)
    assert "startGuideWalkthrough" in guide_page
    assert "开始引导" in guide_page
    assert re.search(r"onClick=\{\(\)\s*=>\s*startGuideWalkthrough\(activeDoc\.slug\)\}", guide_page)


def test_guide_page_resolves_legacy_queries_to_first_task_document():
    guide_page = read(GUIDE_PAGE)
    assert "LEGACY_GUIDE_DOC_SLUGS" in guide_page
    assert "method" in guide_page
    assert "manual" in guide_page
    assert "resolvedRequestedSlug" in guide_page


def test_guide_page_renders_current_document_outline_card():
    guide_page = read(GUIDE_PAGE)
    assert "当前文档目录" in guide_page
    assert "activeDoc.parsed.headings" in guide_page
    assert "heading.level" in guide_page
    assert 'href={`#${heading.id}`}' in guide_page


def test_walkthrough_steps_are_split_by_current_document():
    steps = read(STEPS_MODULE)
    controller = read(CONTROLLER_MODULE)

    assert "GuideWalkthroughDocSlug" in steps
    assert "GUIDE_WALKTHROUGH_STEPS_BY_DOC" in steps
    assert '"create-subject-project"' in steps
    assert '"study-review"' in steps
    assert "getGuideWalkthroughSteps" in steps

    assert "CustomEvent" in controller
    assert "docSlug" in controller
    assert "getGuideWalkthroughSteps" in controller
    assert "resolveGuideWalkthroughCopy(step.sourceRef, options.getDocSlug())" in controller


def test_create_subject_project_guide_ends_before_workbench_to_avoid_pomodoro_gate():
    steps = read(STEPS_MODULE)
    create_doc_steps = re.search(
        r"CREATE_SUBJECT_PROJECT_GUIDE_STEPS: GuideWalkthroughStep\[\] = \[(.*?)\]\s*\n\nexport const STUDY_REVIEW_GUIDE_STEPS",
        steps,
        flags=re.DOTALL,
    )

    assert create_doc_steps
    create_doc_block = create_doc_steps.group(1)
    assert 'id: "import-directory"' in create_doc_block
    assert 'id: "open-workbench"' not in create_doc_block
    assert 'routeHint: "/p/:projectId/workbench"' not in create_doc_block
    assert 'targetAnchor: "workbench-nav"' not in create_doc_block


def test_create_subject_project_guide_opens_default_project_settings_directly():
    steps = read(STEPS_MODULE)
    subject_dashboard = read(SUBJECT_DASHBOARD_PAGE)
    create_doc_steps = re.search(
        r"CREATE_SUBJECT_PROJECT_GUIDE_STEPS: GuideWalkthroughStep\[\] = \[(.*?)\]\s*\n\nexport const STUDY_REVIEW_GUIDE_STEPS",
        steps,
        flags=re.DOTALL,
    )

    assert create_doc_steps
    create_doc_block = create_doc_steps.group(1)
    choose_project_step = re.search(r'\{\s*id:\s*"choose-project".+?popoverSide:\s*"right",\s*\}', create_doc_block, flags=re.DOTALL)
    assert choose_project_step
    assert 'targetAnchor: "subject-project-settings-entry"' in choose_project_step.group(0)
    assert 'id: "open-project-settings"' not in create_doc_block
    assert 'targetAnchor: "subject-project-entry"' not in create_doc_block
    assert 'targetAnchor: "project-settings-nav"' not in create_doc_block
    assert 'data-guide-tour="subject-project-settings-entry"' in subject_dashboard
    assert 'data-guide-tour="subject-project-entry"' not in subject_dashboard


def test_create_subject_project_guide_uses_project_settings_route_not_subject_settings_route():
    steps = read(STEPS_MODULE)
    create_doc_steps = re.search(
        r"CREATE_SUBJECT_PROJECT_GUIDE_STEPS: GuideWalkthroughStep\[\] = \[(.*?)\]\s*\n\nexport const STUDY_REVIEW_GUIDE_STEPS",
        steps,
        flags=re.DOTALL,
    )

    assert create_doc_steps
    create_doc_block = create_doc_steps.group(1)
    for step_id in ["authorize-directory", "import-directory"]:
        step = re.search(r'\{\s*id:\s*"' + re.escape(step_id) + r'".+?popoverSide:\s*"[a-z]+",\s*\}', create_doc_block, flags=re.DOTALL)
        assert step, step_id
        assert 'routeHint: "/p/:projectId/project-settings"' in step.group(0)
        assert 'routeHint: "/p/:projectId/settings"' not in step.group(0)


def test_create_subject_project_guide_sync_step_waits_for_directory_authorization_completion():
    steps = read(STEPS_MODULE)
    project_settings_page = read(PROJECT_SETTINGS_PAGE)
    create_subject_project_doc = read(CREATE_SUBJECT_PROJECT_DOC)

    authorize_step = re.search(r'\{\s*id:\s*"authorize-directory".+?popoverSide:\s*"left",\s*\}', steps, flags=re.DOTALL)
    import_step = re.search(r'\{\s*id:\s*"import-directory".+?popoverSide:\s*"left",\s*\}', steps, flags=re.DOTALL)

    assert authorize_step
    assert import_step
    assert 'advanceOn: "completion-event"' in authorize_step.group(0)
    assert 'advanceOn: "target-click"' not in authorize_step.group(0)
    assert 'heading: "第 3 步：同步目录内容"' in import_step.group(0)
    assert 'targetAnchor: "import-directory-button"' in import_step.group(0)

    assert "completeGuideWalkthroughStep" in project_settings_page
    assert 'completeGuideWalkthroughStep("authorize-directory")' in project_settings_page
    assert 'data-guide-tour="import-directory-button"' in project_settings_page
    assert "同步目录内容" in project_settings_page

    assert "## 第 3 步：同步目录内容" in create_subject_project_doc
    assert "点击“同步目录内容”" in create_subject_project_doc
    assert "点击“导入内容目录”" not in create_subject_project_doc


def test_create_subject_step_source_and_initial_drive_call():
    steps = read(STEPS_MODULE)
    controller = read(CONTROLLER_MODULE)
    assert re.search(
        r'id:\s*"create-subject".+?heading:\s*"第 1 步：创建学科和项目".+?itemIndex:\s*2',
        steps,
        flags=re.DOTALL,
    )
    assert ".drive(" in controller


def test_study_review_guide_resolves_current_project_workbench_route_and_binds_real_actions():
    steps = read(STEPS_MODULE)
    controller = read(CONTROLLER_MODULE)
    learning_object_tree = read(LEARNING_OBJECT_TREE)
    compose_pane = read(COMPOSE_PANE)
    review_pane = read(REVIEW_PANE)

    study_doc_steps = re.search(
        r"STUDY_REVIEW_GUIDE_STEPS: GuideWalkthroughStep\[\] = \[(.*?)\]\s*\n\nexport const GUIDE_WALKTHROUGH_STEPS_BY_DOC",
        steps,
        flags=re.DOTALL,
    )
    assert study_doc_steps
    study_doc_block = study_doc_steps.group(1)

    assert 'routeHint: "/p/:projectId/workbench"' in study_doc_block
    assert 'targetAnchor: "learning-object-tree-item"' in study_doc_block
    study_step_ids = re.findall(r'id:\s*"([^"]+)"', study_doc_block)
    assert study_step_ids == [
        "select-learning-object",
        "add-recall-point",
        "fill-recall-question",
        "fill-recall-answer",
        "submit-learning",
        "submit-review-answer",
        "mark-review-result",
        "submit-review",
    ]

    for step_id in [
        "select-learning-object",
        "add-recall-point",
        "fill-recall-question",
        "fill-recall-answer",
        "submit-learning",
        "submit-review-answer",
        "mark-review-result",
        "submit-review",
    ]:
        step = re.search(r'\{\s*id:\s*"' + re.escape(step_id) + r'".+?popoverSide:\s*"[a-z]+",\s*\}', study_doc_block, flags=re.DOTALL)
        assert step, step_id
        assert 'advanceOn: "completion-event"' in step.group(0)

    assert "resolveGuideRouteHint" in controller
    assert "useAppStore.getState()" in controller
    assert "selectedProjectId" in controller
    assert "recentProjectIds" in controller
    assert '.replace(":projectId",' in controller

    assert 'data-guide-tour="learning-object-tree-item"' in learning_object_tree

    assert "completeGuideWalkthroughStep" in compose_pane
    assert 'completeGuideWalkthroughStep("add-recall-point")' in compose_pane
    assert 'data-guide-tour="recall-question-editor"' in compose_pane
    assert 'data-guide-tour="recall-answer-editor"' in compose_pane
    assert 'completeGuideWalkthroughStep("fill-recall-question")' in compose_pane
    assert 'completeGuideWalkthroughStep("fill-recall-answer")' in compose_pane
    assert 'completeGuideWalkthroughStep("submit-learning")' in compose_pane

    assert "completeGuideWalkthroughStep" in review_pane
    assert 'data-guide-tour="submit-review-answer-button"' in review_pane
    assert 'data-guide-tour="review-memory-choice-buttons"' in review_pane
    assert 'data-guide-tour="submit-review-button"' in review_pane
    assert 'completeGuideWalkthroughStep("submit-review-answer")' in review_pane
    assert 'completeGuideWalkthroughStep("mark-review-result")' in review_pane
    assert 'completeGuideWalkthroughStep("submit-review")' in review_pane


def test_all_source_references_resolve_in_manual():
    document_sections = {slug: parse_document_sections(path) for slug, path in GUIDE_DOCUMENTS.items()}
    steps = parse_steps()
    assert steps, "walkthrough steps should be parseable"

    for step in steps:
        heading = str(step["heading"])
        doc_slug = "study-review" if heading in document_sections["study-review"] else "create-subject-project"
        sections = document_sections[doc_slug]
        assert heading in sections, f"{step['id']} references missing manual heading {heading!r}"
        item_numbers = [step["itemIndex"]] if step["itemIndex"] else step["itemIndexes"]
        if item_numbers:
            items = ordered_items(sections[heading])
            for item_number in item_numbers:
                assert 1 <= int(item_number) <= len(items), f"{step['id']} item {item_number} does not exist under {heading}"


def test_steps_do_not_contain_independent_popover_body_copy():
    steps = read(STEPS_MODULE)
    forbidden_tokens = ["description:", "body:", "content:", "popoverDescription", "popoverBody"]
    for token in forbidden_tokens:
        assert token not in steps


def test_first_release_step_ids_match_contract():
    contract = read(CONTRACT_STEP_MAP)
    contract_ids = re.findall(r"`([a-z0-9-]+)`", contract.split("## Validation Rules", 1)[0])
    expected_ids = [step_id for step_id in FIRST_RELEASE_STEP_IDS if step_id in contract_ids]
    assert expected_ids == FIRST_RELEASE_STEP_IDS
    assert [step["id"] for step in parse_steps()] == FIRST_RELEASE_STEP_IDS


def test_source_reference_metadata_is_exported_for_release_review():
    steps = read(STEPS_MODULE)
    assert "guideWalkthroughSourceReferences" in steps
    for step_id in FIRST_RELEASE_STEP_IDS:
        assert step_id in steps


def test_all_target_anchors_are_present_in_frontend_sources():
    source = frontend_sources()
    for anchor in FIRST_RELEASE_ANCHORS:
        assert has_anchor_coverage(source, anchor)


def test_steps_with_targets_have_fallback_modes_and_anchor_coverage():
    steps = parse_steps()
    source = frontend_sources()
    valid_fallbacks = {"centered-popover", "route-hint", "skip-with-explanation"}
    for step in steps:
        fallback_mode = str(step["fallbackMode"])
        assert fallback_mode in valid_fallbacks, f"{step['id']} must declare a supported fallback"
        anchor = str(step["targetAnchor"])
        if anchor:
            assert has_anchor_coverage(source, anchor), f"{step['id']} target anchor {anchor!r} is missing"


def test_nav_items_support_project_guide_tour_anchors():
    nav_items = read(NAV_ITEMS)
    main_nav = read(MAIN_NAV)
    assert "guideTourAnchor" in nav_items
    assert 'guideTourAnchor: "project-settings-nav"' in nav_items
    assert 'guideTourAnchor: "workbench-nav"' in nav_items
    assert "data-guide-tour={item.guideTourAnchor}" in main_nav


def test_controller_contains_missing_target_fallback_route_hint_and_cleanup():
    controller = read(CONTROLLER_MODULE)
    for symbol in [
        "resolveGuideTargetElement",
        "buildFallbackDriverStep",
        "handleRouteHint",
        "skip-with-explanation",
        "route-hint",
        "cleanupGuideWalkthrough",
    ]:
        assert symbol in controller


def test_walkthrough_action_steps_advance_from_user_actions():
    steps = read(STEPS_MODULE)
    controller = read(CONTROLLER_MODULE)
    projects_page = read(PROJECTS_PAGE)

    create_subject_step = re.search(r'\{\s*id:\s*"create-subject".+?popoverSide:\s*"bottom",\s*\}', steps, flags=re.DOTALL)
    create_submit_step = re.search(r'\{\s*id:\s*"create-subject-submit".+?popoverSide:\s*"top",\s*\}', steps, flags=re.DOTALL)
    assert create_subject_step
    assert create_submit_step
    assert 'advanceOn: "target-click"' in create_subject_step.group(0)
    assert 'advanceOn: "completion-event"' in create_submit_step.group(0)

    assert "completeGuideWalkthroughStep" in controller
    assert "GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT" in controller
    assert re.search(r'addEventListener\(\s*"click"', controller)
    assert "ACTION_STEP_BUTTONS" in controller
    assert '["close"]' in controller

    assert "completeGuideWalkthroughStep" in projects_page
    assert 'completeGuideWalkthroughStep("create-subject-submit")' in projects_page


def test_controller_refreshes_active_steps_without_orphaning_popovers():
    controller = read(CONTROLLER_MODULE)

    assert ".setSteps(" not in controller
    assert "replaceGuideWalkthroughSteps" in controller
    assert ".setConfig({" in controller


def test_walkthrough_can_run_during_pomodoro_and_stops_before_locked_workbench():
    controller = read(CONTROLLER_MODULE)

    assert "shouldEndGuideWalkthroughBeforeWorkbench" in controller
    assert "usePomodoroStore.getState()" in controller
    assert "getPomodoroSnapshot({ enabled: state.enabled, weeklySchedule: state.weeklySchedule, quickPomodoro: state.quickPomodoro }, now)" in controller
    assert "snapshot.shouldRestrictWorkbench && !snapshot.canUseWorkbench" in controller
    assert "describePomodoroPhase" in controller
    assert "showInfoFeedback" in controller
    assert "当前不是学习时间" in controller
    assert "本次引导先到这里" in controller

    start_function = re.search(r"export function startGuideWalkthrough\(.*?\).*?\n\}", controller, flags=re.DOTALL)
    assert start_function
    assert "isGuideWalkthroughBlockedByPomodoro" not in start_function.group(0)
    assert "return true" in start_function.group(0)

    run_function = re.search(r"function runWalkthrough\(.*?\).*?function destroyActiveWalkthrough", controller, flags=re.DOTALL)
    assert run_function
    assert "isGuideWalkthroughBlockedByPomodoro" not in run_function.group(0)

    advance_function = re.search(r"function advanceGuideWalkthroughFromIndex\(.*?function completeActiveGuideWalkthroughStep", controller, flags=re.DOTALL)
    assert advance_function
    assert "shouldEndGuideWalkthroughBeforeWorkbench(nextStep)" in advance_function.group(0)
    assert "cleanupGuideWalkthrough" in advance_function.group(0)

    highlighted_function = re.search(r"onHighlighted: \(element, _driverStep, opts\) => \{.*?popover:", controller, flags=re.DOTALL)
    assert highlighted_function
    assert "event.preventDefault()" in highlighted_function.group(0)
    assert "event.stopPropagation()" in highlighted_function.group(0)


def test_create_subject_submit_step_has_distinct_copy_and_dialog_target():
    steps = read(STEPS_MODULE)
    projects_page = read(PROJECTS_PAGE)
    create_subject_project_doc = read(CREATE_SUBJECT_PROJECT_DOC)

    create_submit_step = re.search(r'\{\s*id:\s*"create-subject-submit".+?popoverSide:\s*"top",\s*\}', steps, flags=re.DOTALL)
    assert create_submit_step
    assert 'popoverTitle: "第 2 步：填写标题并创建学科"' in create_submit_step.group(0)
    assert "填写学科标题后，点击“创建学科”。" in create_subject_project_doc
    assert re.search(r"<DialogContent[^>]+data-guide-tour=\"create-subject-submit\"", projects_page)
