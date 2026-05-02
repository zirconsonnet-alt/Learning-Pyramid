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


def test_fullscreen_printscreen_captures_current_video_frame_into_answer() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "event.key === \"PrintScreen\"" in source
    assert "event.code === \"PrintScreen\"" in source
    assert "captureCurrentFrameIntoAnswer" in source
    assert "captureDisplayedVideoFrameFile" in source
    assert "uploadMediaAsset(projectId, captured.file)" in source
    assert "setAnswerContent((prev) => appendImageBlock(prev, uploaded.assetId))" in source
    assert "PrtScSysRq" in source
