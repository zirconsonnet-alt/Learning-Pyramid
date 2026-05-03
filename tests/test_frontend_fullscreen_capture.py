from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"


def test_fullscreen_capture_supports_tab_reference_picker() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "type CaptureReferencePickerField = \"question\" | \"answer\"" in source
    assert "openCaptureReferencePicker(\"question\")" in source
    assert "openCaptureReferencePicker(\"answer\")" in source
    assert "captureReferencePicker?.field === \"question\"" in source
    assert "captureReferencePicker?.field === \"answer\"" in source
    assert "references: captureReferenceIds" in source


def test_fullscreen_shift_c_captures_current_video_frame_into_answer() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "event.shiftKey" in source
    assert "!event.altKey" in source
    assert "!event.ctrlKey" in source
    assert "!event.metaKey" in source
    assert 'event.code === "KeyC"' in source
    assert "captureCurrentFrameIntoAnswer" in source
    assert "captureDisplayedVideoFrameFile" in source
    assert "uploadMediaAsset(projectId, captured.file)" in source
    assert "setAnswerContent((prev) => appendImageBlock(prev, uploaded.assetId))" in source
    assert "Shift+C" in source
    assert "PrtScSysRq" not in source


def test_playback_hover_menus_keep_clickable_pointer_bridge() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "bottom-full left-1/2 mb-2" not in source
    assert source.count("bottom-full left-1/2 pb-2") >= 2
    assert "group-hover/volume:pointer-events-auto" in source
    assert "group-hover/rate:pointer-events-auto" in source
