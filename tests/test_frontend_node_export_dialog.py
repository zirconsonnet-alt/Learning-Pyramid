from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_EXPORT_CARD = REPO_ROOT / "frontend" / "src" / "views" / "shared" / "NodeExportCard.tsx"


def test_node_export_dialog_uses_compact_export_format_copy() -> None:
    source = NODE_EXPORT_CARD.read_text(encoding="utf-8")

    assert "视频字幕不再由 ASR 生成" not in source
    assert "字幕来源" not in source
    assert "SUPPORTED_SUBTITLE_EXTENSIONS_LABEL" not in source
    assert "导出格式：" in source
    assert "JSON, MD, PDF" in source
    assert 'isExportingRecall ? "导出中..." : "导出"' in source
    assert "导出复述点 JSON" not in source
