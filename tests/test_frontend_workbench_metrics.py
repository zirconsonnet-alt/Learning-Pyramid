from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_STATS = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "workbenchDailyStats.ts"
STUDY_PRESENCE_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "studyPresenceStore.ts"
PROFILE_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "profile.ts"
STUDY_METRICS_SYNC = REPO_ROOT / "frontend" / "src" / "ui" / "studyMetricsSync.ts"
WORKBENCH_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "WorkbenchPage.tsx"
VIDEO_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx"
COMPOSE_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ComposePane.tsx"
REVIEW_PANE = REPO_ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "ReviewPane.tsx"
AI_CHAT_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx"
POMODORO_ACTIVITY_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "pomodoroActivityStore.ts"
VIDEO_WATCH_PROGRESS_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "videoWatchProgress.ts"
INSTANCES_API = REPO_ROOT / "frontend" / "src" / "ui" / "api" / "instances.ts"


def test_workbench_metric_store_defines_web_presence_partition() -> None:
    source = WORKBENCH_STATS.read_text(encoding="utf-8")

    assert "export type StudyActivityKind = \"video\" | \"recallEntry\" | \"review\" | \"aiQa\"" in source
    assert "webPresenceMs: number" in source
    assert "videoMs: number" in source
    assert "recallEntryMs: number" in source
    assert "distractionMs: number" in source
    assert "presenceRanges: StudyMetricRange[]" in source
    assert "recallEntryRanges: StudyMetricRange[]" in source
    assert "loadDailyWebPresenceMetrics" in source
    assert "recordWebPresenceActivity" in source
    assert "summarizeWebMetricPartition" in source
    assert "webPresenceMs: summary.videoMs + summary.recallEntryMs + summary.reviewMs + summary.aiQaMs + summary.distractionMs" in source


def test_workbench_metric_sync_uses_new_schema_fields() -> None:
    profile_source = PROFILE_API.read_text(encoding="utf-8")
    sync_source = STUDY_METRICS_SYNC.read_text(encoding="utf-8")

    assert "schemaVersion: z.number().int().positive().default(2)" in profile_source
    assert "webPresenceMs: z.number().int().nonnegative()" in profile_source
    assert "presenceRanges: z.array(StudyMetricRangeSchema)" in profile_source
    assert "recallEntryMs: z.number().int().nonnegative()" in profile_source
    assert "recallEntryRanges: z.array(StudyMetricRangeSchema)" in profile_source
    assert "distractionMs: z.number().int().nonnegative()" in profile_source
    assert "isPartitionComplete: z.boolean().default(false)" in profile_source
    assert "listDailyStudyMetricEntries" in sync_source
    assert "mergeDailyStudyMetricEntries" in sync_source


def test_workbench_status_card_uses_objective_metric_rows_only() -> None:
    source = WORKBENCH_PAGE.read_text(encoding="utf-8")

    assert "网页驻留" in source
    assert "网页驻留 {formatDurationCompact(todayStats.webPresenceMs)}" not in source
    assert '<StatusMetricRow label="网页驻留" value={formatDurationCompact(todayStats.webPresenceMs)} emphasize />' in source
    assert "视频观看" in source
    assert "复述点录入" in source
    assert "复习用时" in source
    assert "AI 问答" in source
    assert "走神时间" in source
    assert "有效学习时长" not in source
    assert "学习驻留" not in source
    assert "客观专注率" not in source
    assert "内容接触" not in source
    assert "复述点构建" not in source
    assert "录入复述点数" not in source
    assert "复习复述点数" not in source
    assert "Math.max(todayPresenceStats.presenceMs, todayStats.effectiveMs)" not in source


def test_recorders_use_new_metric_categories() -> None:
    video_source = VIDEO_PANE.read_text(encoding="utf-8")
    compose_source = COMPOSE_PANE.read_text(encoding="utf-8")
    review_source = REVIEW_PANE.read_text(encoding="utf-8")
    ai_source = AI_CHAT_PAGE.read_text(encoding="utf-8")

    assert 'recordStudyActivity(projectId, "video"' in video_source
    assert 'touchDailyStudyActivity(projectId, "recallEntry"' in video_source
    assert 'touchDailyStudyActivity(projectId, "aiQa"' in video_source
    assert 'touchDailyStudyActivity(projectId, "recallEntry"' in compose_source
    assert 'touchDailyStudyActivity(projectId, "review"' in review_source
    assert 'touchDailyStudyActivity(pid, "aiQa"' in ai_source


def test_presence_tracker_records_presence_without_effective_fallback() -> None:
    source = STUDY_PRESENCE_STORE.read_text(encoding="utf-8")

    assert "recordWebPresenceActivity(projectId" in source
    assert "presenceMs: current.presenceMs + safeDeltaMs" in source
    assert "effectiveMs" not in source


def test_pomodoro_completion_does_not_create_workbench_web_presence() -> None:
    source = POMODORO_ACTIVITY_STORE.read_text(encoding="utf-8")

    assert "recordEffectiveStudyActivity" not in source
    assert "recordWebPresenceActivity" not in source
    assert "recordPomodoroActivity" in source


def test_distraction_and_overlap_are_derived_from_presence_partition() -> None:
    source = WORKBENCH_STATS.read_text(encoding="utf-8")

    assert "distractionMs: sumRanges(unassignedPresenceRanges)" in source
    assert 'for (const key of ["aiQaRanges", "reviewRanges", "recallEntryRanges", "videoRanges"] as const)' in source
    assert "resolved[key] = intersectRanges(stored[key], unassignedPresenceRanges)" in source
    assert "unassignedPresenceRanges = subtractRanges(unassignedPresenceRanges, resolved[key])" in source


def test_hidden_pages_and_paused_video_do_not_accumulate_active_metrics() -> None:
    presence_source = STUDY_PRESENCE_STORE.read_text(encoding="utf-8")
    video_source = VIDEO_PANE.read_text(encoding="utf-8")

    assert 'document.visibilityState !== "visible"' in presence_source
    assert "now - lastInteractionAtMs > ACTIVE_WINDOW_MS" in presence_source
    assert "if (video.paused || video.ended)" in video_source
    assert "lastPlaybackTrackedAtRef.current = null" in video_source


def test_project_video_progress_uses_persistent_instance_watch_facts() -> None:
    progress_source = VIDEO_WATCH_PROGRESS_STORE.read_text(encoding="utf-8")
    instances_source = INSTANCES_API.read_text(encoding="utf-8")
    workbench_source = WORKBENCH_PAGE.read_text(encoding="utf-8")
    video_source = VIDEO_PANE.read_text(encoding="utf-8")

    assert "completedAt" in progress_source
    assert "markVideoWatchProgressCompleted" in progress_source
    assert "syncVideoWatchProgressRange" in progress_source
    assert "loadVideoWatchProgressMap" in progress_source
    assert "syncVideoWatchProgressRange" in instances_source
    assert "fetchVideoWatchProgressMap" in instances_source
    assert "fetchVideoWatchProgressMap(pid, instanceIds" in workbench_source
    assert "loadVideoWatchProgressMap(pid, instanceIds" in workbench_source
    assert "markVideoWatchProgressCompleted(projectId, instanceId" in video_source
    assert "syncVideoWatchProgressRange(projectId, instanceId" in video_source
