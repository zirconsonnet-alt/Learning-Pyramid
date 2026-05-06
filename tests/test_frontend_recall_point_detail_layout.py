from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "frontend" / "src" / "views" / "recallPoints" / "RecallPointPage.tsx"


def test_recall_point_detail_moves_editing_into_content_card() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "概览与修改" not in source
    assert "锚点位置" not in source
    assert "onClick={openAnchorEditor}" in source
    assert "const [editingContent" in source
    assert "<CardTitle>当前内容</CardTitle>" in source
    content_card_source = source[source.index("<CardTitle>当前内容</CardTitle>"):]
    assert "<RichContentEditor" in content_card_source
    assert "保存修改" in content_card_source


def test_recall_point_detail_uses_shared_detail_page_card_style() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]' in source
    assert '<aside className="xl:sticky xl:top-28 xl:self-start">' in source
    assert "RecallPointSummaryCard" in source
    assert "RecallPointContentCard" in source
    assert "theme-card-main" not in source
    assert "theme-card-header" not in source
