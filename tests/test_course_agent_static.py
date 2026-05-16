import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CourseAgentStaticTest(unittest.TestCase):
    def test_course_agent_uses_project_ask_instead_of_raw_chat_completions(self) -> None:
        source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")

        self.assertIn("askProjectLlmStream", source)
        self.assertNotIn("askProjectLlmChatCompletion", source)
        self.assertNotIn("/llm/chat-completions", source)

    def test_course_agent_includes_caller_system_prompt(self) -> None:
        source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")

        self.assertIn("params.systemPrompt?.trim()", source)
        self.assertIn("systemPrompt,", source)

    def test_workbench_ai_surfaces_identify_as_xuebao(self) -> None:
        video_source = (ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx").read_text(
            encoding="utf-8"
        )
        pet_source = (
            ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "WorkbenchPetAssistant.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("你叫雪豹", video_source)
        self.assertIn("你叫雪豹", pet_source)

    def test_video_frame_capture_is_shared(self) -> None:
        video_source = (ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx").read_text(
            encoding="utf-8"
        )
        shared_source = (ROOT / "frontend" / "src" / "ui" / "media" / "videoFrameCapture.ts").read_text(encoding="utf-8")

        self.assertIn("captureDisplayedVideoFrame", shared_source)
        self.assertIn("captureVideoFrameAt", shared_source)
        self.assertIn("@/ui/media/videoFrameCapture", video_source)
        self.assertNotIn("function captureDisplayedVideoFrameBlob", video_source)

    def test_ai_chat_course_context_attaches_frame_and_does_not_fallback(self) -> None:
        source = (ROOT / "frontend" / "src" / "views" / "ai" / "AiChatPage.tsx").read_text(encoding="utf-8")
        course_block = source[source.index("if (courseContext) {") : source.index("const resolvedSupplementalContext")]

        self.assertIn("captureAiChatCourseFrame", source)
        self.assertIn("initialFrame", course_block)
        self.assertNotIn("catch (error)", course_block)

    def test_course_agent_explicitly_retries_text_when_image_input_is_unsupported(self) -> None:
        source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")

        self.assertIn("isImageInputUnsupportedError", source)
        self.assertIn("retryWithoutImageInputs", source)
        self.assertIn("未使用视频帧", source)
        self.assertIn("本轮回答未使用视频帧", source)

    def test_workbench_pet_can_export_self_contained_html_context_without_llm(self) -> None:
        course_source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")
        pet_source = (
            ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "WorkbenchPetAssistant.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("buildCourseAgentContextPackage", course_source)
        self.assertIn("buildCourseAgentContextHtml", course_source)
        self.assertIn("获取上下文", pet_source)
        self.assertIn("downloadContextHtml", pet_source)
        self.assertIn("contextExportMode", pet_source)
        self.assertIn("已整理当前上下文，未调用 LLM", pet_source)


if __name__ == "__main__":
    unittest.main()
