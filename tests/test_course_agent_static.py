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

    def test_workbench_course_evidence_sections_use_consistent_label(self) -> None:
        video_source = (ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx").read_text(
            encoding="utf-8"
        )
        pet_source = (
            ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "WorkbenchPetAssistant.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("依据片段", video_source)
        self.assertIn("依据片段", pet_source)

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

    def test_workbench_pet_can_prepare_context_after_user_message_without_llm(self) -> None:
        course_source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")
        pet_source = (
            ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "WorkbenchPetAssistant.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("buildCourseAgentContextPackage", course_source)
        self.assertIn("buildCourseAgentContextText", course_source)
        self.assertNotIn("buildCourseAgentContextHtml", course_source)
        self.assertIn("获取上下文", pet_source)
        self.assertIn("contextCopy", pet_source)
        self.assertIn("已整理当前上下文，未调用 LLM", pet_source)
        self.assertIn("复制文本", pet_source)
        self.assertIn("复制图片", pet_source)
        self.assertNotIn("copyContextText", pet_source)
        self.assertNotIn("copyContextImage", pet_source)
        self.assertNotIn("先输入一个问题，再复制文本。", pet_source)
        self.assertNotIn("downloadContextHtml", pet_source)
        self.assertNotIn("contextExportMode", pet_source)

    def test_context_text_is_task_first_and_does_not_repeat_html_export_language(self) -> None:
        source = (ROOT / "frontend" / "src" / "ui" / "llm" / "courseAgent.ts").read_text(encoding="utf-8")
        context_text_block = source[
            source.index("export function buildCourseAgentContextText") : source.index("function askCourseAgentStream")
        ]

        self.assertIn("请直接回答用户问题", source)
        self.assertIn("buildCourseAgentContextText", source)
        self.assertIn("复述点上下文", source)
        self.assertIn("相关字幕", source)
        self.assertNotIn("实例 ID", context_text_block)
        self.assertNotIn("材料 ID", context_text_block)
        self.assertNotIn("材料来源", context_text_block)
        self.assertNotIn("Instance ID:", source)
        self.assertNotIn("Material ID:", source)
        self.assertNotIn("Material source kind:", source)
        self.assertNotIn("HTML 文件", source)
        self.assertNotIn("buildCourseAgentContextHtml", source)
        self.assertNotIn("可复制给模型的完整提示", source)
        self.assertNotIn("<h2>引用片段</h2>", source)

    def test_video_assistant_shortcut_hint_only_lists_supported_newline_shortcut(self) -> None:
        source = (ROOT / "frontend" / "src" / "views" / "workbench" / "components" / "VideoPane.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("Enter 提交问题，Shift+Enter 换行。视频助手会读取当前画面和附近字幕。", source)
        self.assertNotIn("Shift+Enter / Ctrl+Enter 换行", source)
        self.assertNotIn("assistantStatus ??\n                            \"Enter 提交问题", source)


if __name__ == "__main__":
    unittest.main()
