from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUBTITLE_TOOL_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "subtitleTool" / "SubtitleToolPage.tsx"


def test_subtitle_tool_page_removes_status_pill_and_summary_copy() -> None:
    source = SUBTITLE_TOOL_PAGE.read_text(encoding="utf-8")

    assert "字幕工具" in source
    assert "准备资源 → 选择目录 → 生成 → 回到 LearningPyramid" in source
    assert "下载 → 选目录 → 生成 → 回到 LearningPyramid" not in source
    assert "可以直接下载" not in source
    assert "lp-subtitle-tool-status" not in source
    assert "lp-subtitle-tool-summary" not in source
    assert "离线扫描视频目录，用内置 ffmpeg + whisper.cpp 生成同目录同名 `.srt` 字幕，支持可选 NVIDIA CUDA GPU 加速。" not in source
