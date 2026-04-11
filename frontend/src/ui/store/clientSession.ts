import { clearCachedAsrSubtitleChunks } from "@/ui/localMedia/asrSubtitleChunkCache"
import { clearCachedAsrTranscripts } from "@/ui/localMedia/asrTranscriptCache"
import { useAiChatStore } from "@/ui/store/aiChatStore"
import { useAppStore } from "@/ui/store/appStore"
import { useAsrStore } from "@/ui/store/asrStore"
import { useFeedbackStore } from "@/ui/store/feedbackStore"
import { useGlobalConfigStore } from "@/ui/store/globalConfigStore"
import { useLearningPlanStore } from "@/ui/store/learningPlanStore"
import { usePomodoroDailyReportStore } from "@/ui/store/pomodoroDailyReportStore"
import { clearAllPlaybackResumeState } from "@/ui/store/playbackResume"
import { usePomodoroStore } from "@/ui/store/pomodoroStore"
import { clearAllStudyPresenceStats } from "@/ui/store/studyPresenceStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { clearAllVideoWatchCoverageState } from "@/ui/store/videoWatchCoverage"
import { clearAllDailyWorkbenchStats } from "@/ui/store/workbenchDailyStats"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { DEFAULT_THEME_PRESET_ID } from "@/ui/theme/themePresets"

export function clearPersistedClientState() {
  useAiChatStore.getState().reset()
  useAppStore.getState().reset()
  useAsrStore.getState().reset()
  useThemeStore.getState().setTheme(DEFAULT_THEME_PRESET_ID)
  useGlobalConfigStore.getState().resetDefaultProjectReviewTemplate()
  usePomodoroDailyReportStore.getState().reset()
  useLearningPlanStore.getState().reset()
  usePomodoroStore.getState().reset()
  useWorkbenchStore.getState().clearAll()
  useFeedbackStore.getState().clear()
  useAiChatStore.persist.clearStorage()
  useAppStore.persist.clearStorage()
  useAsrStore.persist.clearStorage()
  useThemeStore.persist.clearStorage()
  useGlobalConfigStore.persist.clearStorage()
  usePomodoroDailyReportStore.persist.clearStorage()
  useLearningPlanStore.persist.clearStorage()
  usePomodoroStore.persist.clearStorage()
  useWorkbenchStore.persist.clearStorage()
  void clearCachedAsrSubtitleChunks()
  void clearCachedAsrTranscripts()
  clearAllPlaybackResumeState()
  clearAllVideoWatchCoverageState()
  clearAllDailyWorkbenchStats()
  clearAllStudyPresenceStats()
}
