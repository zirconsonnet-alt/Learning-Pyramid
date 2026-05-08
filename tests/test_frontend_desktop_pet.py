from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_PET = ROOT / "frontend" / "src" / "ui" / "components" / "DesktopPet.tsx"
HOME_PAGE = ROOT / "frontend" / "src" / "views" / "home" / "HomePage.tsx"
WORKBENCH_PAGE = ROOT / "frontend" / "src" / "views" / "workbench" / "WorkbenchPage.tsx"
WORKBENCH_PET_ASSISTANT = ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "WorkbenchPetAssistant.tsx"
INDEX_CSS = ROOT / "frontend" / "src" / "index.css"
ASSETS_DIR = ROOT / "frontend" / "src" / "assets"


def test_desktop_pet_component_and_assets_exist() -> None:
    assert DESKTOP_PET.exists()

    source = DESKTOP_PET.read_text(encoding="utf-8")

    assert 'import xuebaoIdle from "@/assets/xuebao-idle.gif"' in source
    assert 'import xuebaoRotation from "@/assets/xuebao-rotation.gif"' in source
    assert 'import xuebaoStand from "@/assets/xuebao-stand.png"' in source
    assert 'aria-label="雪豹桌面宠物"' in source
    assert 'page?: "home" | "workbench"' in source
    assert "children?: ReactNode" in source
    assert "plm-desktop-pet-popover" in source
    assert "has-popover" in source
    assert "isPinned" in source
    assert 'aria-expanded={isPinned}' in source
    assert "plm-desktop-pet-popover-close" in source

    expected_assets = [
        "xuebao-idle.gif",
        "xuebao-rotation.gif",
        "xuebao-stand.png",
    ]
    for asset_name in expected_assets:
        asset = ASSETS_DIR / asset_name
        assert asset.exists()
        assert asset.stat().st_size > 0


def test_homepage_and_workbench_mount_desktop_pet_on_right_side() -> None:
    home_source = HOME_PAGE.read_text(encoding="utf-8")
    workbench_source = WORKBENCH_PAGE.read_text(encoding="utf-8")
    css = INDEX_CSS.read_text(encoding="utf-8")

    assert 'import { DesktopPet } from "@/ui/components/DesktopPet"' in home_source
    assert '<DesktopPet page="home" />' in home_source

    assert 'import { DesktopPet } from "@/ui/components/DesktopPet"' in workbench_source
    assert 'import { WorkbenchPetAssistant } from "@/views/workbench/components/WorkbenchPetAssistant"' in workbench_source
    assert '<DesktopPet page="workbench">' in workbench_source
    assert "<WorkbenchPetAssistant" in workbench_source

    assert ".plm-desktop-pet" in css
    assert ".plm-desktop-pet-button" in css
    assert ".plm-desktop-pet-popover" in css
    assert ".plm-desktop-pet.has-popover:hover .plm-desktop-pet-popover" in css
    assert ".plm-desktop-pet.has-popover.is-pinned .plm-desktop-pet-popover" in css
    assert ".plm-desktop-pet-popover-close" in css
    assert ".plm-desktop-pet.is-home" in css
    assert ".plm-desktop-pet.is-workbench" in css
    assert "right: clamp(16px, 2vw, 28px);" in css


def test_workbench_pet_assistant_uses_ai_context_sources() -> None:
    assert WORKBENCH_PET_ASSISTANT.exists()

    source = WORKBENCH_PET_ASSISTANT.read_text(encoding="utf-8")

    assert 'import { askProjectLlmStream } from "@/ui/api/system"' in source
    assert 'import { askCourseAgent } from "@/ui/llm/courseAgent"' in source
    assert 'import { MarkdownRichText } from "@/ui/components/MarkdownRichText"' in source
    assert "touchDailyStudyActivity(projectId, \"aiQa\"" in source
    assert "loadSubtitleDocumentForInstance" in source
    assert "问问雪豹" in source
