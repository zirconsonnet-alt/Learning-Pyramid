from __future__ import annotations

import os
from dataclasses import dataclass

from backend.system.runtime_features import current_runtime_features


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, int(default))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = int(default)
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class CommunityGuardrailConfig:
    enabled: bool
    create_group_min_account_age_seconds: int
    create_group_window_seconds: int
    create_group_max_actions_per_window: int
    join_group_min_account_age_seconds: int
    join_group_window_seconds: int
    join_group_max_actions_per_window: int
    join_request_min_account_age_seconds: int
    join_request_window_seconds: int
    join_request_max_actions_per_window: int
    post_min_account_age_seconds: int
    post_window_seconds: int
    post_max_actions_per_window: int
    comment_min_account_age_seconds: int
    comment_window_seconds: int
    comment_max_actions_per_window: int


def current_community_guardrail_config() -> CommunityGuardrailConfig:
    hosted = current_runtime_features().app_mode == "hosted"
    return CommunityGuardrailConfig(
        enabled=_env_bool("PLM_ENABLE_COMMUNITY_GUARDRAILS", hosted),
        create_group_min_account_age_seconds=_env_int("PLM_STUDY_GROUP_CREATE_MIN_ACCOUNT_AGE_SECONDS", 600, minimum=0),
        create_group_window_seconds=_env_int("PLM_STUDY_GROUP_CREATE_WINDOW_SECONDS", 3600, minimum=1),
        create_group_max_actions_per_window=_env_int("PLM_STUDY_GROUP_CREATE_MAX_ACTIONS_PER_WINDOW", 2, minimum=0),
        join_group_min_account_age_seconds=_env_int("PLM_STUDY_GROUP_JOIN_MIN_ACCOUNT_AGE_SECONDS", 120, minimum=0),
        join_group_window_seconds=_env_int("PLM_STUDY_GROUP_JOIN_WINDOW_SECONDS", 900, minimum=1),
        join_group_max_actions_per_window=_env_int("PLM_STUDY_GROUP_JOIN_MAX_ACTIONS_PER_WINDOW", 8, minimum=0),
        join_request_min_account_age_seconds=_env_int("PLM_STUDY_GROUP_JOIN_REQUEST_MIN_ACCOUNT_AGE_SECONDS", 120, minimum=0),
        join_request_window_seconds=_env_int("PLM_STUDY_GROUP_JOIN_REQUEST_WINDOW_SECONDS", 1800, minimum=1),
        join_request_max_actions_per_window=_env_int("PLM_STUDY_GROUP_JOIN_REQUEST_MAX_ACTIONS_PER_WINDOW", 5, minimum=0),
        post_min_account_age_seconds=_env_int("PLM_STUDY_GROUP_POST_MIN_ACCOUNT_AGE_SECONDS", 180, minimum=0),
        post_window_seconds=_env_int("PLM_STUDY_GROUP_POST_WINDOW_SECONDS", 600, minimum=1),
        post_max_actions_per_window=_env_int("PLM_STUDY_GROUP_POST_MAX_ACTIONS_PER_WINDOW", 5, minimum=0),
        comment_min_account_age_seconds=_env_int("PLM_STUDY_GROUP_COMMENT_MIN_ACCOUNT_AGE_SECONDS", 120, minimum=0),
        comment_window_seconds=_env_int("PLM_STUDY_GROUP_COMMENT_WINDOW_SECONDS", 600, minimum=1),
        comment_max_actions_per_window=_env_int("PLM_STUDY_GROUP_COMMENT_MAX_ACTIONS_PER_WINDOW", 12, minimum=0),
    )
