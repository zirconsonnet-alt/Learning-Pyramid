from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RICH_CONTENT_RENDERER = REPO_ROOT / "frontend" / "src" / "ui" / "components" / "RichContentRenderer.tsx"
RICH_CONTENT_EDITOR = REPO_ROOT / "frontend" / "src" / "ui" / "components" / "RichContentEditor.tsx"
MARKDOWN_RICH_TEXT = REPO_ROOT / "frontend" / "src" / "ui" / "components" / "MarkdownRichText.tsx"


def test_rich_content_renderer_renders_text_blocks_as_markdown_and_latex() -> None:
    renderer_source = RICH_CONTENT_RENDERER.read_text(encoding="utf-8")
    markdown_source = MARKDOWN_RICH_TEXT.read_text(encoding="utf-8")

    assert 'import { MarkdownRichText } from "@/ui/components/MarkdownRichText"' in renderer_source
    assert "<MarkdownRichText" in renderer_source
    assert "text={block.text}" in renderer_source
    assert "remarkMath" in markdown_source
    assert "rehypeKatex" in markdown_source
    assert "remarkGfm" in markdown_source


def test_rich_content_editor_keeps_possible_edits_as_raw_source_text() -> None:
    editor_source = RICH_CONTENT_EDITOR.read_text(encoding="utf-8")

    assert "MarkdownRichText" not in editor_source
    assert "const text = richContentText(value)" in editor_source
    assert "value={text}" in editor_source
    assert "onTextChange(event.target.value)" in editor_source
