import { useAppStore } from "@/ui/store/appStore"
import { useFeedbackStore } from "@/ui/store/feedbackStore"
import { clearAllPlaybackResumeState } from "@/ui/store/playbackResume"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"

export function clearPersistedClientState() {
  useAppStore.getState().reset()
  useWorkbenchStore.getState().clearAll()
  useFeedbackStore.getState().clear()
  useAppStore.persist.clearStorage()
  useWorkbenchStore.persist.clearStorage()
  clearAllPlaybackResumeState()
}
