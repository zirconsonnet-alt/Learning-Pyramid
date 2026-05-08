from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER = REPO_ROOT / "frontend" / "src" / "router.tsx"


def test_project_dropdown_destinations_are_eager_routes() -> None:
    router_source = ROUTER.read_text(encoding="utf-8")
    high_frequency_pages = [
        "AiChatPage",
        "ReviewRecommendationsPage",
        "ProjectSettingsPage",
        "StructureViewPage",
    ]

    for page in high_frequency_pages:
        assert f"const {page} = lazyRoute(" not in router_source
        assert f'import {{ {page} }} from "' in router_source
