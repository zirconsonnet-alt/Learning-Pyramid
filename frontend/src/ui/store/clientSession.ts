import { clearCachedAsrSubtitleChunks } from "@/ui/localMedia/asrSubtitleChunkCache"
import { clearCachedAsrTranscripts } from "@/ui/localMedia/asrTranscriptCache"
import { useAiChatStore } from "@/ui/store/aiChatStore"
import { useAppStore } from "@/ui/store/appStore"
import { useAsrStore } from "@/ui/store/asrStore"
import { useFeedbackStore } from "@/ui/store/feedbackStore"
import { clearAllPlaybackResumeState } from "@/ui/store/playbackResume"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"

export function clearPersistedClientState() {
  useAiChatStore.getState().reset()
  useAppStore.getState().reset()
  useAsrStore.getState().reset()
  useWorkbenchStore.getState().clearAll()
  useFeedbackStore.getState().clear()
  useAiChatStore.persist.clearStorage()
  useAppStore.persist.clearStorage()
  useAsrStore.persist.clearStorage()
  useWorkbenchStore.persist.clearStorage()
  void clearCachedAsrSubtitleChunks()
  void clearCachedAsrTranscripts()
  clearAllPlaybackResumeState()
}
