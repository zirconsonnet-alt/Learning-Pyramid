import unittest
from typing import Any
from unittest.mock import patch

from backend.models.enums import MaterialSourceKind, ProjectType
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem


class ProjectLlmMultimodalTest(unittest.TestCase):
    def test_project_llm_ask_sends_current_frame_as_image_message_part(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Video AI",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        api.update_global_llm_settings(
            base_url="https://llm.example.test/v1",
            model_name="vision-model",
            api_key="test-key",
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_post_json(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float) -> dict[str, Any]:
            captured_payloads.append(payload)
            return {"choices": [{"message": {"content": "回答"}}]}

        frame = {
            "imageDataUrl": "data:image/png;base64,AAAA",
            "mimeType": "image/png",
            "timeMs": 5380,
        }

        with patch.object(SystemAPI, "_http_post_json", side_effect=fake_post_json):
            content = api.request_project_llm_text(
                project_id=project_id,
                user_prompt="解释一下这里",
                image_inputs=[frame],
            )

        self.assertEqual("回答", content)
        self.assertEqual(1, len(captured_payloads))
        messages = captured_payloads[0]["messages"]
        self.assertIsInstance(messages, list)
        user_message = messages[-1]
        self.assertIsInstance(user_message, dict)
        self.assertEqual("user", user_message["role"])
        content_parts = user_message["content"]
        self.assertIsInstance(content_parts, list)
        self.assertEqual({"type": "text", "text": "解释一下这里"}, content_parts[0])
        self.assertEqual(
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            content_parts[1],
        )

        debug = api.get_latest_project_llm_debug(project_id)
        self.assertIsNotNone(debug)
        debug_messages = debug["messages"]  # type: ignore[index]
        self.assertIsInstance(debug_messages, list)
        debug_content = "\n".join(str(message["content"]) for message in debug_messages)
        self.assertIn("[image:image/png at 5380ms]", debug_content)
        self.assertNotIn("data:image/png;base64,AAAA", debug_content)

    def test_project_llm_stream_sends_current_frame_as_image_message_part(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Streaming Video AI",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        api.update_global_llm_settings(
            base_url="https://llm.example.test/v1",
            model_name="vision-model",
            api_key="test-key",
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_stream(*, url: str, payload: dict[str, object], api_key: str | None, timeout_sec: float):
            captured_payloads.append(payload)
            yield "流式"
            yield "回答"

        frame = {
            "imageDataUrl": "data:image/jpeg;base64,BBBB",
            "mimeType": "image/jpeg",
            "timeMs": 9010,
        }

        with patch.object(SystemAPI, "_http_post_json_stream_text_chunks", side_effect=fake_stream):
            chunks = list(
                api.request_project_llm_text_stream(
                    project_id=project_id,
                    user_prompt="这张图在讲什么",
                    image_inputs=[frame],
                )
            )

        self.assertEqual(["流式", "回答"], chunks)
        self.assertEqual(1, len(captured_payloads))
        self.assertTrue(captured_payloads[0]["stream"])
        messages = captured_payloads[0]["messages"]
        self.assertIsInstance(messages, list)
        content_parts = messages[-1]["content"]
        self.assertIsInstance(content_parts, list)
        self.assertEqual(
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,BBBB"}},
            content_parts[1],
        )

    def test_project_llm_image_time_must_be_integer(self) -> None:
        api = SystemAPI(InMemorySystem())
        project_id = api.create_project(
            "Invalid Frame Time",
            initial_source_kind=MaterialSourceKind.MANUAL,
            initial_project_type=ProjectType.COURSE,
        )
        api.update_global_llm_settings(
            base_url="https://llm.example.test/v1",
            model_name="vision-model",
            api_key="test-key",
        )

        with self.assertRaisesRegex(PreconditionFailure, "timeMs must be an integer"):
            api.request_project_llm_text(
                project_id=project_id,
                user_prompt="解释一下这里",
                image_inputs=[{"imageDataUrl": "data:image/png;base64,AAAA", "timeMs": "bad"}],
            )


if __name__ == "__main__":
    unittest.main()
