from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POMODORO_STORE = REPO_ROOT / "frontend" / "src" / "ui" / "store" / "pomodoroStore.ts"
POMODORO_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx"
LOCAL_MEDIA = REPO_ROOT / "frontend" / "src" / "ui" / "localMedia" / "projectDirectory.ts"
GLOBAL_SETTINGS_PAGE = REPO_ROOT / "frontend" / "src" / "views" / "settings" / "GlobalSettingsPage.tsx"
USER_MANUAL = REPO_ROOT / "docs" / "learningpyramid-user-manual.md"


def test_pomodoro_store_supports_multiple_non_overlapping_day_plans() -> None:
    source = POMODORO_STORE.read_text(encoding="utf-8")

    assert "export type PomodoroPlanSchedule" in source
    assert "plans: PomodoroPlanSchedule[]" in source
    assert "validatePomodoroWeekSchedule" in source
    assert "getActivePomodoroDayPlans" in source
    assert "version: 7" in source


def test_pomodoro_page_can_edit_multiple_plans_and_warn_conflicts() -> None:
    source = POMODORO_PAGE.read_text(encoding="utf-8")

    assert "pomodoroDrafts" in source
    assert "addPomodoroDraftPlan" in source
    assert "removePomodoroDraftPlan" in source
    assert "planConflictMessages" in source
    assert "新增计划" in source
    assert "删除计划" in source
    assert "计划时间冲突" in source


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


def test_user_manual_documents_local_rest_music_directory_scope() -> None:
    manual_source = USER_MANUAL.read_text(encoding="utf-8")

    assert "休息音乐目录" in manual_source
    assert "本地浏览器授权" in manual_source
    assert "不会上传到服务端" in manual_source
