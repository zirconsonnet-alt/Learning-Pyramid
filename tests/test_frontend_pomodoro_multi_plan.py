from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POMODORO_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "pomodoroStore.ts"
POMODORO_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx"
POMODORO_ROUTING = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "pomodoroRouting.ts"
FRONTEND_ROUTER = REPO_ROOT / "frontend" / "src" / "router.tsx"
APP_SHELL = REPO_ROOT / "frontend" / "src" / "shell" / "AppShell.tsx"
NAV_ITEMS = REPO_ROOT / "frontend" / "src" / "shell" / "navItems.ts"
LOCAL_MEDIA = REPO_ROOT / "frontend" / "src" / "ui" / "localMedia" / "projectDirectory.ts"
POMODORO_REST_MUSIC_PLAYER = REPO_ROOT / "frontend" / "src" / "ui" / "pomodoroRestMusicPlayer.ts"
GLOBAL_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "GlobalSettingsPage.tsx"
USER_MANUAL = REPO_ROOT / "docs" / "learningpyramid-user-manual.md"


def test_pomodoro_store_supports_multiple_non_overlapping_day_plans() -> None:
    source = POMODORO_STORE.read_text(encoding="utf-8")

    assert "export type PomodoroPlanSchedule" in source
    assert "plans: PomodoroPlanSchedule[]" in source
    assert "validatePomodoroWeekSchedule" in source
    assert "getActivePomodoroDayPlans" in source
    assert "version: 8" in source


def test_pomodoro_store_supports_quick_pomodoro_session() -> None:
    source = POMODORO_STORE.read_text(encoding="utf-8")

    assert "export type QuickPomodoroSession" in source
    assert "QUICK_POMODORO_PREPARE_MS = 10_000" in source
    assert "QUICK_POMODORO_FOCUS_MS = 25 * 60_000" in source
    assert "quickPomodoro: QuickPomodoroSession | null" in source
    assert "startQuickPomodoro: (projectId?: string | null) => QuickPomodoroSession" in source
    assert "clearQuickPomodoro: () => void" in source
    assert "buildQuickPomodoroPlan" in source
    assert "quickPomodoro && now < quickPomodoro.endAtMs" in source
    assert "getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now)" in POMODORO_PAGE.read_text(encoding="utf-8")


def test_pomodoro_page_exposes_quick_pomodoro_action() -> None:
    source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in source
    assert "const startQuickPomodoro = usePomodoroStore((state) => state.startQuickPomodoro)" in source
    assert "function handleStartQuickPomodoro()" in source
    assert "startQuickPomodoro(selectedProjectId)" in source
    assert 'const isFocusRunning = snapshot.status === "running" && snapshot.phase === "focus"' in source
    assert "disabled={Boolean(activeQuickPomodoro) || isFocusRunning}" in source
    assert "新建小番茄" in source
    assert "10 秒后开始 25 分钟学习" in source


def test_quick_pomodoro_feeds_shell_gate_and_fullscreen_previews() -> None:
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    gate_source = (REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroWorkbenchGate.tsx").read_text(encoding="utf-8")
    video_pane_source = (REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx").read_text(encoding="utf-8")

    assert "const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in app_shell_source
    assert "getPomodoroSnapshot({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in app_shell_source
    assert "getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in app_shell_source
    assert "const showPomodoroShortcut = pomodoroEnabled || Boolean(activePomodoroQuickSession)" in app_shell_source

    assert "const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in gate_source
    assert "const pomodoroActive = enabled || Boolean(activeQuickPomodoro)" in gate_source
    assert "getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now)" in gate_source

    assert "const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in video_pane_source
    assert "getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in video_pane_source


def test_pomodoro_page_can_edit_multiple_plans_and_warn_conflicts() -> None:
    source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "pomodoroDrafts" in source
    assert "addPomodoroDraftPlan" in source
    assert "removePomodoroDraftPlan" in source
    assert "planConflictMessages" in source
    assert "新增计划" in source
    assert "删除计划" in source
    assert "计划时间冲突" in source


def test_pomodoro_plan_editing_uses_dedicated_route() -> None:
    routing_source = POMODORO_ROUTING.read_text(encoding="utf-8")
    router_source = FRONTEND_ROUTER.read_text(encoding="utf-8")
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "buildPomodoroEditPath" in routing_source
    assert 'return "/pomodoro/edit"' in routing_source
    assert 'path: "/pomodoro/edit"' in router_source
    assert "to={buildPomodoroEditPath({ addPlan: true })}" in page_source
    assert "to={buildPomodoroEditPath()}" in page_source
    assert "setIsScheduleDetailOpen" not in page_source


def test_pomodoro_entry_stays_as_header_shortcut_not_global_menu_item() -> None:
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")
    nav_source = NAV_ITEMS.read_text(encoding="utf-8")
    global_nav_block = nav_source[nav_source.index("const BASE_GLOBAL_NAV_ITEMS"):nav_source.index("export function getGlobalNavItems")]

    assert "to={buildPomodoroPath()}" in app_shell_source
    assert 'to: "/pomodoro"' not in global_nav_block
    assert "番茄钟" not in global_nav_block


def test_pomodoro_preview_warns_before_last_focus_enters_rest() -> None:
    source = POMODORO_STORE.read_text(encoding="utf-8")

    assert "const finalBreakPreview" in source
    assert 'snapshot.segment.phase === "focus"' in source
    assert 'phase: "break"' in source
    assert "snapshot.currentPlan.breakPrompt" in source


def test_pomodoro_project_prompt_cards_stay_in_one_horizontal_scroll_row() -> None:
    source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "pomodoro-project-prompt-scroll" in source
    assert "overflow-x-auto" in source
    assert "flex-nowrap" in source
    assert "min-w-[20rem]" in source
    assert "xl:grid-cols-3" not in source


def test_pomodoro_rest_music_directory_can_be_bound_and_played_during_breaks() -> None:
    local_media_source = LOCAL_MEDIA.read_text(encoding="utf-8")
    settings_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")
    pomodoro_page_source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "usePomodoroRestMusicDirectoryBinding" in local_media_source
    assert "scanPomodoroRestMusicDirectory" in local_media_source
    assert "resolvePomodoroRestMusicFile" in local_media_source
    assert "POMODORO_REST_MUSIC_EXTENSIONS" in local_media_source

    assert "usePomodoroRestMusicDirectoryBinding" in settings_source
    assert "休息音乐目录" in settings_source
    assert "选择音乐目录" in settings_source
    assert "清除音乐目录" in settings_source

    assert "RestMusicPlayer" in pomodoro_page_source
    assert "scanPomodoroRestMusicDirectory" in pomodoro_page_source
    assert "resolvePomodoroRestMusicFile" in pomodoro_page_source
    assert 'snapshot.phase === "break"' in pomodoro_page_source


def test_pomodoro_rest_music_playback_survives_route_changes() -> None:
    player_source = POMODORO_REST_MUSIC_PLAYER.read_text(encoding="utf-8")
    pomodoro_page_source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "pomodoroRestMusicState" in player_source
    assert "subscribePomodoroRestMusicPlayer" in player_source
    assert "playPomodoroRestMusicTrack" in player_source
    assert "pausePomodoroRestMusic" in player_source
    assert "isRestPhaseActive" in player_source
    assert "audio.pause()" not in pomodoro_page_source[pomodoro_page_source.index("function RestMusicPlayer"):]
    assert "revokePomodoroRestMusicObjectUrl" not in pomodoro_page_source


def test_user_manual_documents_local_rest_music_directory_scope() -> None:
    manual_source = USER_MANUAL.read_text(encoding="utf-8")

    assert "休息音乐目录" in manual_source
    assert "本地浏览器授权" in manual_source
    assert "不会上传到服务端" in manual_source
    assert "切换到 AI 问答等其他路由会继续播放" in manual_source
