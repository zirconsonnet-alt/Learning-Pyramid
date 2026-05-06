from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POMODORO_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "pomodoroStore.ts"
POMODORO_AUDIO = REPO_ROOT / "frontend" / "src" / "ui" / "pomodoroAudio.ts"
PROFILE_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "profile.ts"
GLOBAL_SETTINGS_SYNC = REPO_ROOT / "frontend" / "src" / "ui" / "globalSettingsSync.ts"
POMODORO_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx"
POMODORO_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroSettingsPage.tsx"
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"
POMODORO_ROUTING = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "pomodoroRouting.ts"
POMODORO_WALLPAPER = REPO_ROOT / "frontend" / "src" / "ui" / "pomodoroWallpaper.ts"
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
    assert "version: 10" in source


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
    video_pane_source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in app_shell_source
    assert "getPomodoroSnapshot({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in app_shell_source
    assert "getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in app_shell_source
    assert "const showPomodoroShortcut = pomodoroEnabled || Boolean(activePomodoroQuickSession)" in app_shell_source

    assert "const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in gate_source
    assert "const pomodoroActive = enabled || Boolean(activeQuickPomodoro)" in gate_source
    assert "getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now)" in gate_source

    assert "const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)" in video_pane_source
    assert "getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow)" in video_pane_source


def test_pomodoro_store_supports_random_micro_break_settings() -> None:
    source = POMODORO_STORE.read_text(encoding="utf-8")

    assert "export type RandomMicroBreakSettings" in source
    assert "DEFAULT_RANDOM_MICRO_BREAK_SETTINGS" in source
    assert "normalizeRandomMicroBreakSettings" in source
    assert "microBreaks: RandomMicroBreakSettings" in source
    assert "setMicroBreakSettings: (settings: Partial<RandomMicroBreakSettings>) => void" in source
    assert "microBreaks: normalizeRandomMicroBreakSettings(settings.microBreaks ?? state.microBreaks)" in source
    assert "microBreaks: normalizeRandomMicroBreakSettings(raw.microBreaks)" in source


def test_frontend_global_settings_sync_includes_pomodoro_micro_breaks() -> None:
    profile_source = PROFILE_API.read_text(encoding="utf-8")
    sync_source = GLOBAL_SETTINGS_SYNC.read_text(encoding="utf-8")

    assert "const UserPomodoroMicroBreaksSchema" in profile_source
    assert "minIntervalSeconds: z.number().int().min(30).max(3600)" in profile_source
    assert "maxIntervalSeconds: z.number().int().min(30).max(3600)" in profile_source
    assert "durationSeconds: z.number().int().min(5).max(300)" in profile_source
    assert "microBreaks: UserPomodoroMicroBreaksSchema.optional().default" in profile_source
    assert "microBreaks?: z.input<typeof UserPomodoroMicroBreaksSchema>" in profile_source
    assert "microBreaks: settings.pomodoro.microBreaks" in sync_source


def test_pomodoro_audio_exports_micro_break_reminder_sound() -> None:
    source = POMODORO_AUDIO.read_text(encoding="utf-8")

    assert "export async function playPomodoroMicroBreakReminderSound()" in source
    assert "ensureAudioContextReady()" in source
    assert "microBreakReminderNotes" in source


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

    assert "buildPomodoroPlanPath" in routing_source
    assert 'return `/pomodoro/plans/${encodeURIComponent(planId)}`' in routing_source
    assert 'path: "/pomodoro/plans/:planId"' in router_source
    assert "useParams" in page_source
    assert "const activePomodoroDraft =" in page_source
    assert 'data-pomodoro-plan-overview' in page_source
    assert 'data-pomodoro-plan-detail' in page_source
    assert "to={buildPomodoroPlanPath(pomodoroDraft.id)}" in page_source
    assert "nav(buildPomodoroPlanPath(nextDraft.id))" in page_source
    assert "isScheduleEditRoute" not in page_source
    assert "to={buildPomodoroEditPath()}" not in page_source
    assert "setIsScheduleDetailOpen" not in page_source


def test_pomodoro_plan_detail_route_omits_timer_overview_shell() -> None:
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    detail_return_start = page_source.index("if (activePlanId) {")
    overview_start = page_source.index("data-pomodoro-session-controls")
    detail_route_source = page_source[detail_return_start:overview_start]

    assert detail_return_start < overview_start
    assert "return (" in detail_route_source
    assert "data-pomodoro-plan-detail" in detail_route_source
    assert "<PhaseBadge snapshot={snapshot} />" not in detail_route_source
    assert "{headlineCountdown}" not in detail_route_source
    assert "MetricTile label=" not in detail_route_source
    assert "<RestMusicPlayer" not in detail_route_source
    assert "返回番茄计划" in detail_route_source


def test_pomodoro_settings_use_dedicated_route_and_default_prompts() -> None:
    store_source = POMODORO_STORE.read_text(encoding="utf-8")
    routing_source = POMODORO_ROUTING.read_text(encoding="utf-8")
    router_source = FRONTEND_ROUTER.read_text(encoding="utf-8")
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")
    manual_source = USER_MANUAL.read_text(encoding="utf-8")

    assert "defaultFocusPrompt: string" in store_source
    assert "defaultBreakPrompt: string" in store_source
    assert "setDefaultPrompts" in store_source
    assert "version: 10" in store_source

    assert "buildPomodoroSettingsPath" in routing_source
    assert 'return "/pomodoro/settings"' in routing_source
    assert 'path: "/pomodoro/settings"' in router_source
    assert "PomodoroSettingsPage" in router_source

    assert "to={buildPomodoroSettingsPath()}" in page_source
    assert "番茄钟设置" in page_source
    assert "defaultFocusPrompt" in page_source
    assert "defaultBreakPrompt" in page_source
    assert "appendDefaultPomodoroPlanDraft(prev, defaultPrompts)" in page_source

    assert "默认学习提示词" in settings_source
    assert "默认休息提示词" in settings_source
    assert "setDefaultPrompts" in settings_source
    assert "保存设置" in settings_source
    assert "默认学习提示词" in manual_source
    assert "默认休息提示词" in manual_source


def test_pomodoro_session_controls_keep_settings_entry_visible() -> None:
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")

    session_controls = page_source[
        page_source.index("data-pomodoro-session-controls"):page_source.index('<MetricTile label="今日开始"')
    ]
    primary_buttons = session_controls[session_controls.index('className="flex flex-wrap gap-3"'):]

    assert 'aria-label="打开番茄钟设置"' in session_controls
    assert "to={buildPomodoroSettingsPath()}" in session_controls
    assert "Settings2" in session_controls
    assert primary_buttons.index("{quickPomodoroButtonLabel}") < primary_buttons.index("番茄钟设置")
    assert "handleToggleTransitionSound" not in session_controls
    assert "handleTestSound" not in session_controls
    assert "关闭铃声" not in session_controls
    assert "测试铃声" not in session_controls
    assert "snapshot.canUseWorkbench && preferredWorkbenchPath" in session_controls
    assert "<RestMusicPlayer isRestPhase={isRestPhase} />" in page_source

    assert "buildPomodoroSettingsPath" not in app_shell_source
    assert 'aria-label="打开番茄钟设置"' not in app_shell_source


def test_pomodoro_header_keeps_phase_label_next_to_countdown_without_extra_summary() -> None:
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    session_controls = page_source[
        page_source.index("data-pomodoro-session-controls"):page_source.index('<MetricTile label="今日开始"')
    ]
    header_block = session_controls[
        session_controls.index("<PhaseBadge snapshot={snapshot} />"):session_controls.index('className="flex flex-wrap gap-3"')
    ]

    assert header_block.index("<PhaseBadge snapshot={snapshot} />") < header_block.index("{headlineCountdown}")
    assert "`剩余 ${headlineCountdown}`" not in session_controls
    assert "`距离开始 ${headlineCountdown}`" not in session_controls
    assert '"按排程运行"' not in session_controls
    assert '"铃声开"' not in session_controls
    assert '"铃声关"' not in session_controls
    assert "describeProjectLabel(snapshot.currentProjectId" not in session_controls


def test_pomodoro_settings_page_edits_random_micro_break_preferences() -> None:
    settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "microBreakDraft" in settings_source
    assert "setMicroBreakSettings" in settings_source
    assert "validateMicroBreakDraft" in settings_source
    assert "随机微休息" in settings_source
    assert "pomodoro-micro-break-enabled" in settings_source
    assert "pomodoro-micro-break-min-interval" in settings_source
    assert "pomodoro-micro-break-max-interval" in settings_source
    assert "pomodoro-micro-break-duration" in settings_source
    assert "最长间隔不能小于最短间隔" in settings_source
    assert "恢复微休息默认值" in settings_source


def test_pomodoro_settings_payloads_preserve_random_micro_breaks() -> None:
    page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")
    global_settings_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")

    assert "const microBreaks = usePomodoroStore((state) => state.microBreaks)" in page_source
    page_pomodoro_payload = page_source[page_source.index("pomodoro: {"):page_source.index("}", page_source.index("pomodoro: {"))]
    assert "microBreaks," in page_pomodoro_payload
    assert "setSettings({ enabled, weeklySchedule: draftSchedule, transitionSoundEnabled, microBreaks })" in page_source

    assert "microBreaks: nextMicroBreaks" in settings_source
    assert "setMicroBreakSettings(nextMicroBreaks)" in settings_source

    assert "const microBreaks = usePomodoroStore((state) => state.microBreaks)" in global_settings_source
    global_pomodoro_payload = global_settings_source[
        global_settings_source.index("pomodoro: {"):global_settings_source.index("}", global_settings_source.index("pomodoro: {"))
    ]
    assert "microBreaks," in global_pomodoro_payload


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


def test_micro_break_overlay_uses_dark_gradient_backdrop() -> None:
    video_pane_source = VIDEO_PANE.read_text(encoding="utf-8")
    css_source = (REPO_ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert "pomodoro-micro-break-overlay" in video_pane_source
    assert "pomodoro-micro-break-card" in video_pane_source
    assert "bg-black/58" not in video_pane_source[video_pane_source.index("{showMicroBreakOverlay ? ("):]
    assert "@keyframes plmMicroBreakBackdrop" in css_source
    assert "@keyframes plmMicroBreakCard" in css_source
    assert ".pomodoro-micro-break-overlay" in css_source
    assert "radial-gradient(circle at center" in css_source
    assert "rgba(0, 0, 0, 0.98)" in css_source


def test_pomodoro_rest_music_directory_settings_live_on_pomodoro_settings_page() -> None:
    local_media_source = LOCAL_MEDIA.read_text(encoding="utf-8")
    settings_source = GLOBAL_SETTINGS_PAGE.read_text(encoding="utf-8")
    pomodoro_settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")
    pomodoro_page_source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "usePomodoroRestMusicDirectoryBinding" in local_media_source
    assert "scanPomodoroRestMusicDirectory" in local_media_source
    assert "resolvePomodoroRestMusicFile" in local_media_source
    assert "POMODORO_REST_MUSIC_EXTENSIONS" in local_media_source

    assert "usePomodoroRestMusicDirectoryBinding" not in settings_source
    assert "休息音乐目录" not in settings_source
    assert "系统接入中心" not in settings_source

    assert "usePomodoroRestMusicDirectoryBinding" in pomodoro_settings_source
    assert "休息音乐目录" in pomodoro_settings_source
    assert "选择音乐目录" in pomodoro_settings_source
    assert "清除音乐目录" in pomodoro_settings_source

    assert "RestMusicPlayer" in pomodoro_page_source
    assert "scanPomodoroRestMusicDirectory" in pomodoro_page_source
    assert "resolvePomodoroRestMusicFile" in pomodoro_page_source
    assert 'snapshot.phase === "break"' in pomodoro_page_source
    assert "buildPomodoroSettingsPath()" in pomodoro_page_source
    assert "番茄钟设置" in pomodoro_page_source
    assert "全局设置" not in pomodoro_page_source[pomodoro_page_source.index("function RestMusicPlayer"):]


def test_pomodoro_wallpaper_is_displayed_on_page_and_managed_in_settings() -> None:
    pomodoro_page_source = POMODORO_PAGE.read_text(encoding="utf-8")
    pomodoro_settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")
    wallpaper_source = POMODORO_WALLPAPER.read_text(encoding="utf-8")
    manual_source = USER_MANUAL.read_text(encoding="utf-8")

    assert "POMODORO_WALLPAPER_DB_NAME" in wallpaper_source
    assert "learningpyramid-pomodoro-wallpaper" in wallpaper_source
    assert "indexedDB.open" in wallpaper_source
    assert "readPomodoroWallpaperBlob" in wallpaper_source
    assert "savePomodoroWallpaperBlob" in wallpaper_source
    assert "removePomodoroWallpaperBlob" in wallpaper_source

    assert "readPomodoroWallpaperBlob" in pomodoro_page_source
    assert "URL.createObjectURL" in pomodoro_page_source
    assert "URL.revokeObjectURL" in pomodoro_page_source
    assert "data-pomodoro-wallpaper-backdrop" in pomodoro_page_source
    assert 'data-pomodoro-wallpaper-scope="page"' in pomodoro_page_source
    assert "wallpaperInputRef" not in pomodoro_page_source
    assert "savePomodoroWallpaperBlob" not in pomodoro_page_source
    assert "removePomodoroWallpaperBlob" not in pomodoro_page_source
    assert "更换壁纸" not in pomodoro_page_source
    assert "移除壁纸" not in pomodoro_page_source

    assert "wallpaperInputRef" in pomodoro_settings_source
    assert 'accept="image/*"' in pomodoro_settings_source
    assert "readPomodoroWallpaperBlob" in pomodoro_settings_source
    assert "savePomodoroWallpaperBlob" in pomodoro_settings_source
    assert "removePomodoroWallpaperBlob" in pomodoro_settings_source
    assert "更换壁纸" in pomodoro_settings_source
    assert "移除壁纸" in pomodoro_settings_source
    assert "只保存在当前浏览器，不会上传服务器，也不会影响其他页面。" in pomodoro_settings_source
    assert "番茄钟设置页可以管理本地壁纸" in manual_source


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
    assert "番茄钟设置" in manual_source
    assert "本地浏览器授权" in manual_source
    assert "不会上传到服务端" in manual_source
    assert "切换到 AI 问答等其他路由会继续播放" in manual_source


def test_player_ai_gate_uses_membership_summary_and_member_only_message() -> None:
    source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "useMembershipSummary" in source
    assert "playerAiMemberBlocked" in source
    assert "canAskCourseAssistant =" in source
    assert "!playerAiMemberBlocked" in source[source.index("const canAskCourseAssistant ="):source.index("const deferredCaptureReferenceQuery")]
    assert "视频助手是会员专属功能" in source


def test_pomodoro_pages_gate_non_members_and_preserve_member_controls() -> None:
    pomodoro_source = POMODORO_PAGE.read_text(encoding="utf-8")
    settings_source = POMODORO_SETTINGS_PAGE.read_text(encoding="utf-8")

    for source in (pomodoro_source, settings_source):
        assert "useMembershipSummary" in source
        assert "MemberOnlyFeatureNotice" in source
        assert "pomodoroMemberBlocked" in source

    assert "开启番茄钟" in pomodoro_source
    assert "新建小番茄" in pomodoro_source
    assert "保存设置" in settings_source


def test_member_only_gate_is_limited_to_protected_frontend_surfaces() -> None:
    router_source = FRONTEND_ROUTER.read_text(encoding="utf-8")
    app_shell_source = APP_SHELL.read_text(encoding="utf-8")

    assert "MemberOnlyFeatureNotice" not in router_source
    assert "useMembershipSummary" not in router_source
    assert "MemberOnlyFeatureNotice" not in app_shell_source
    assert "useMembershipSummary" not in app_shell_source
