import type { CourseAgentInitialFrame, CourseAgentRecallContext } from "@/ui/llm/courseAgent"

export type WorkbenchAiContextSnapshot = {
  captureRecallContext: CourseAgentRecallContext | null
  reviewRecallContext: CourseAgentRecallContext | null
}

export type VideoPaneHandle = {
  captureCurrentFrameForAi: () => Promise<CourseAgentInitialFrame | null>
}
