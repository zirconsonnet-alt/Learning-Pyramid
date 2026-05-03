import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
GUIDE_PAGE = SRC / "views" / "guide" / "GuidePage.tsx"
APP_SHELL = SRC / "shell" / "AppShell.tsx"
NAV_ITEMS = SRC / "shell" / "navItems.ts"
MAIN_NAV = SRC / "shell" / "MainNav.tsx"
WALKTHROUGH_DIR = SRC / "ui" / "guideWalkthrough"
COPY_MODULE = WALKTHROUGH_DIR / "guideWalkthroughCopy.ts"
STEPS_MODULE = WALKTHROUGH_DIR / "guideWalkthroughSteps.ts"
CONTROLLER_MODULE = WALKTHROUGH_DIR / "guideWalkthroughController.ts"
MANUAL = ROOT / "docs" / "learningpyramid-user-manual.md"
CONTRACT_STEP_MAP = ROOT / "specs" / "003-driver-page-guide" / "contracts" / "walkthrough-step-map.md"


FIRST_RELEASE_STEP_IDS = [
    "create-subject",
    "create-subject-submit",
    "choose-project",
    "open-project-settings",
    "authorize-directory",
    "import-directory",
    "open-workbench",
    "select-learning-object",
    "add-recall-point",
    "submit-learning",
    "do-review",
]

FIRST_RELEASE_ANCHORS = [
    "new-subject-button",
    "create-subject-submit",
    "subject-project-entry",
    "project-settings-nav",
    "authorize-directory-button",
    "import-directory-button",
    "workbench-nav",
    "learning-object-tree",
    "add-recall-point-button",
    "submit-learning-button",
    "review-pane",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def frontend_sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SRC.rglob("*") if path.suffix in {".ts", ".tsx"})


def has_anchor_coverage(source: str, anchor: str) -> bool:
    return f'data-guide-tour="{anchor}"' in source or f'guideTourAnchor: "{anchor}"' in source


def parse_manual_sections() -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in read(MANUAL).splitlines():
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


def test_copy_module_exports_manual_source_constants():
    copy_source = read(COPY_MODULE)
    assert "docs/learningpyramid-user-manual.md" in copy_source
    assert "userManualMarkdown" in copy_source
    assert "resolveGuideWalkthroughCopy" in copy_source


def test_guide_page_removes_method_document_and_keeps_manual_default():
    guide_page = read(GUIDE_PAGE)
    assert "plm-method-guide.md?raw" not in guide_page
    assert 'slug: "method"' not in guide_page
    assert 'slug: "manual"' in guide_page
    assert "userManualMarkdown" in guide_page


def test_guide_page_renders_start_action_wired_to_walkthrough_api():
    guide_page = read(GUIDE_PAGE)
    assert "startGuideWalkthrough" in guide_page
    assert "开始引导" in guide_page
    assert re.search(r"onClick=\{\(\)\s*=>\s*startGuideWalkthrough\(\)\}", guide_page)


def test_guide_page_resolves_legacy_method_query_to_manual():
    guide_page = read(GUIDE_PAGE)
    assert "LEGACY_GUIDE_DOC_SLUGS" in guide_page
    assert "method" in guide_page
    assert "resolvedRequestedSlug" in guide_page


def test_create_subject_step_source_and_initial_drive_call():
    steps = read(STEPS_MODULE)
    controller = read(CONTROLLER_MODULE)
    assert re.search(
        r'id:\s*"create-subject".+?heading:\s*"第 1 步：创建学科和项目".+?itemIndex:\s*2',
        steps,
        flags=re.DOTALL,
    )
    assert ".drive(" in controller


def test_all_source_references_resolve_in_manual():
    sections = parse_manual_sections()
    steps = parse_steps()
    assert steps, "walkthrough steps should be parseable"

    for step in steps:
        heading = str(step["heading"])
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
