from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from backend.models.errors import PreconditionFailure
from backend.models.types import Timestamp


DEFAULT_GLOBAL_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GLOBAL_LLM_MODEL_NAME = "gpt-4o-mini"
DEFAULT_LLM_PROMPT_ASSEMBLY_MODE = "system"
LLM_PROMPT_ASSEMBLY_MODES = frozenset({"system", "user_concat"})


def normalize_llm_prompt_assembly_mode(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return DEFAULT_LLM_PROMPT_ASSEMBLY_MODE
    if text == "user":
        text = "user_concat"
    if text not in LLM_PROMPT_ASSEMBLY_MODES:
        raise PreconditionFailure("LLM prompt assembly mode must be one of system, user_concat")
    return text


@dataclass(frozen=True, slots=True)
class GlobalLlmSettings:
    base_url: str
    model_name: str
    api_key: Optional[str]
    prompt_assembly_mode: str
    updated_at: Timestamp

    def validate_write_time(self) -> None:
        base_url = str(self.base_url or "")
        model_name = str(self.model_name or "")

        if not base_url.strip():
            raise PreconditionFailure("GlobalLlmSettings.base_url must be non-empty")
        if base_url != base_url.strip():
            raise PreconditionFailure("GlobalLlmSettings.base_url must not contain leading/trailing whitespace")

        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise PreconditionFailure("GlobalLlmSettings.base_url must be an absolute http(s) URL")

        if not model_name.strip():
            raise PreconditionFailure("GlobalLlmSettings.model_name must be non-empty")
        if model_name != model_name.strip():
            raise PreconditionFailure("GlobalLlmSettings.model_name must not contain leading/trailing whitespace")

        if self.api_key is not None and str(self.api_key) != str(self.api_key).strip():
            raise PreconditionFailure("GlobalLlmSettings.api_key must not contain leading/trailing whitespace")

        normalize_llm_prompt_assembly_mode(self.prompt_assembly_mode)
