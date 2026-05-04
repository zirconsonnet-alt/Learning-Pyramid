from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"
COMPOSE_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ComposePane.tsx"
VIDEO_PLAYBACK_RATE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "videoPlaybackRate.ts"
POMODORO_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "pomodoroStore.ts"
POMODORO_AUDIO = REPO_ROOT / "frontend" / "src" / "ui" / "pomodoroAudio.ts"


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


def test_video_playback_rate_remembers_last_selected_rate() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert 'from "@/ui/store/videoPlaybackRate"' in source
    storage_source = VIDEO_PLAYBACK_RATE.read_text(encoding="utf-8")

    assert "VIDEO_PLAYBACK_RATE_STORAGE_KEY" in storage_source
    assert "loadVideoPlaybackRate" in storage_source
    assert "saveVideoPlaybackRate" in storage_source
    assert "normalizeVideoPlaybackRate" in storage_source
    assert "const [playbackRate, setPlaybackRate] = useState(() => loadVideoPlaybackRate())" in source
    assert "const rememberedPlaybackRate = loadVideoPlaybackRate()" in source
    assert "video.playbackRate = rememberedPlaybackRate" in source
    assert "saveVideoPlaybackRate(normalizedRate)" in source
    assert "setPlaybackRate(loadVideoPlaybackRate())" in source
    assert "setPlaybackRate(1)" not in source


def test_pomodoro_micro_break_focus_fullscreen_schedules_random_countdown() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "getPomodoroSnapshot" in source
    assert "const pomodoroMicroBreaks = usePomodoroStore((state) => state.microBreaks)" in source
    assert "const pomodoroSnapshot = useMemo(" in source
    assert 'pomodoroSnapshot.status === "running"' in source
    assert 'pomodoroSnapshot.phase === "focus"' in source
    assert "isShellFullscreen" in source
    assert "createRandomMicroBreakDelayMs" in source
    assert "segmentKey" in source
    assert "targetAtMs" in source
    assert "countdownEndsAtMs" in source
    assert "setMicroBreakState({ status: \"scheduled\"" in source
    assert "window.setTimeout(handleMicroBreakTrigger" in source
    assert "window.setInterval" in source


def test_pomodoro_micro_break_reminder_pauses_and_conditionally_resumes_video() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "playPomodoroMicroBreakReminderSound" in source
    assert "wasPlayingBeforeBreak" in source
    assert "const wasPlayingBeforeBreak = !video.paused && !video.ended" in source
    assert "video.pause()" in source
    assert "if (completedState.wasPlayingBeforeBreak)" in source
    assert "void video.play().catch" in source

    audio_source = POMODORO_AUDIO.read_text(encoding="utf-8")
    assert "playPomodoroMicroBreakReminderSound" in audio_source


def test_pomodoro_micro_break_skips_final_three_minutes_and_transition_prompt_overlap() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "POMODORO_MICRO_BREAK_FORBIDDEN_WINDOW_MS = 3 * 60_000" in source
    assert "POMODORO_TRANSITION_PREVIEW_WINDOW_MS = 10_000" in source
    assert "forbiddenAfterMs" in source
    assert "forbiddenAfterMs = pomodoroNow + pomodoroSnapshot.segmentRemainingMs - POMODORO_MICRO_BREAK_FORBIDDEN_WINDOW_MS" in source
    assert "if (targetAtMs >= forbiddenAfterMs) return null" in source
    assert "showFullscreenFocusPreview" in source
    assert "showFullscreenBreakPreview" in source
    assert "showMicroBreakOverlay" in source


def test_pomodoro_micro_break_cancels_on_fullscreen_exit_and_ineligible_state_without_resume() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "cancelMicroBreak(\"fullscreen_exit\")" in source
    assert "cancelMicroBreak(\"pomodoro_ineligible\")" in source
    assert "cancelMicroBreak(\"settings_disabled\")" in source
    assert "cancelMicroBreak(\"video_unavailable\")" in source
    assert "cancelMicroBreak(\"route_change\")" in source
    assert "return () => cancelMicroBreak(\"route_change\")" in source
    assert "canceled-break no-resume" in source
