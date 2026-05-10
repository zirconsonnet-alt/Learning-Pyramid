import os
import re

from backend.models.errors import PreconditionFailure

DEFAULT_POMODORO_TTS_VOICE = "zh-CN-XiaoxiaoNeural"
MAX_POMODORO_TTS_TEXT_LENGTH = 200


class PomodoroTtsUnavailable(RuntimeError):
    pass


def normalize_pomodoro_tts_text(value: str | None) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        raise PreconditionFailure("pomodoro TTS text must be non-empty")
    if len(text) > MAX_POMODORO_TTS_TEXT_LENGTH:
        raise PreconditionFailure(f"pomodoro TTS text must be at most {MAX_POMODORO_TTS_TEXT_LENGTH} characters")
    return text


def _pomodoro_tts_voice() -> str:
    text = str(os.getenv("LEARNINGPYRAMID_POMODORO_TTS_VOICE") or "").strip()
    return text or DEFAULT_POMODORO_TTS_VOICE


async def synthesize_pomodoro_prompt_audio(text: str) -> bytes:
    normalized_text = normalize_pomodoro_tts_text(text)
    try:
        import edge_tts  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on deployment environment
        raise PomodoroTtsUnavailable("edge-tts is not installed") from exc

    audio_bytes = bytearray()
    try:
        communicate = edge_tts.Communicate(
            normalized_text,
            voice=_pomodoro_tts_voice(),
        )
        async for chunk in communicate.stream():
            if isinstance(chunk, dict) and chunk.get("type") == "audio":
                payload = chunk.get("data")
                if isinstance(payload, (bytes, bytearray)):
                    audio_bytes.extend(payload)
    except Exception as exc:
        raise PomodoroTtsUnavailable("pomodoro TTS service is unavailable") from exc

    if not audio_bytes:
        raise PomodoroTtsUnavailable("edge-tts returned empty audio")
    return bytes(audio_bytes)
