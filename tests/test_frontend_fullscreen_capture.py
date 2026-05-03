from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"
COMPOSE_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ComposePane.tsx"


def test_fullscreen_capture_supports_tab_reference_picker() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "type CaptureReferencePickerField = \"question\" | \"answer\"" in source
    assert "openCaptureReferencePicker(\"question\")" in source
    assert "openCaptureReferencePicker(\"answer\")" in source
    assert "captureReferencePicker?.field === \"question\"" in source
    assert "captureReferencePicker?.field === \"answer\"" in source
    assert "references: captureReferenceIds" in source


def test_fullscreen_ctrl_alt_captures_current_video_frame_into_answer() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "const isFrameCaptureModifierKey =" in source
    assert 'event.key === "Control"' in source
    assert 'event.key === "Alt"' in source
    assert 'event.code === "ControlLeft"' in source
    assert 'event.code === "ControlRight"' in source
    assert 'event.code === "AltLeft"' in source
    assert 'event.code === "AltRight"' in source
    assert "event.ctrlKey" in source
    assert "event.altKey" in source
    assert "!event.shiftKey" in source
    assert "!event.metaKey" in source
    assert "!event.repeat" in source
    assert "captureCurrentFrameIntoAnswer" in source
    assert "captureDisplayedVideoFrameFile" in source
    assert "uploadMediaAsset(projectId, captured.file)" in source
    assert "setAnswerContent((prev) => appendImageBlock(prev, uploaded.assetId))" in source
    assert "Ctrl+Alt" in source
    assert "Shift+C" not in source
    assert 'event.code === "KeyC"' not in source
    assert "PrtScSysRq" not in source


def test_fullscreen_capture_shift_enter_keeps_newline_in_question_and_answer() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")
    question_start = source.index('placeholder="输入复述点问题')
    answer_start = source.index('placeholder="输入答案或你的复述内容')
    question_keydown_block = source[question_start:source.index("referencePicker={", question_start)]
    answer_keydown_block = source[answer_start:source.index("referencePicker={", answer_start)]

    assert 'event.key === "Enter" && !(event.ctrlKey || event.metaKey || event.shiftKey)' in question_keydown_block
    assert 'event.key === "Enter" && !(event.ctrlKey || event.metaKey || event.shiftKey)' in answer_keydown_block


def test_fullscreen_capture_selects_newly_added_compose_draft() -> None:
    source = COMPOSE_PANE.read_text(encoding="utf-8")

    assert "previousDraftScopeRef" in source
    assert "previous.scopeKey !== taskScopeKey" in source
    assert "drafts.length <= previous.count" in source
    assert "const newestDraft = drafts[drafts.length - 1]" in source
    assert "setActiveDraftId(newestDraft.localId)" in source


def test_playback_hover_menus_keep_clickable_pointer_bridge() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "bottom-full left-1/2 mb-2" not in source
    assert source.count("bottom-full left-1/2 pb-2") >= 2
    assert "group-hover/volume:pointer-events-auto" in source
    assert "group-hover/rate:pointer-events-auto" in source
