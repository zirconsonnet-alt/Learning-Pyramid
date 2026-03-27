from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.system.auth_rate_limit_store import AuthRateLimitDecision, AuthRateLimitStore
from backend.system.auth_store import AuthUser
from backend.system.community_guardrails import CommunityGuardrailConfig


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CommunityGuardrailAgeDecision:
    allowed: bool
    retry_after_seconds: int


def evaluate_account_age_guardrail(*, user: AuthUser, minimum_age_seconds: int) -> CommunityGuardrailAgeDecision:
    if minimum_age_seconds <= 0:
        return CommunityGuardrailAgeDecision(allowed=True, retry_after_seconds=0)
    created_at = _parse_dt(user.created_at)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    age_seconds = max(0, int((now - created_at).total_seconds()))
    if age_seconds >= int(minimum_age_seconds):
        return CommunityGuardrailAgeDecision(allowed=True, retry_after_seconds=0)
    return CommunityGuardrailAgeDecision(allowed=False, retry_after_seconds=max(1, int(minimum_age_seconds) - age_seconds))


def check_create_group_allowed(
    store: AuthRateLimitStore,
    config: CommunityGuardrailConfig,
    *,
    user: AuthUser,
) -> tuple[CommunityGuardrailAgeDecision, AuthRateLimitDecision]:
    age = evaluate_account_age_guardrail(user=user, minimum_age_seconds=config.create_group_min_account_age_seconds)
    rate = store.check_scope_allowed(
        scope="study_group_create_user",
        raw_key=user.user_id,
        limit=config.create_group_max_actions_per_window,
        window_seconds=config.create_group_window_seconds,
    )
    return age, rate


def record_create_group(store: AuthRateLimitStore, config: CommunityGuardrailConfig, *, user: AuthUser) -> None:
    store.record_scope_action(
        scope="study_group_create_user",
        raw_key=user.user_id,
        window_seconds=config.create_group_window_seconds,
    )


def check_join_group_allowed(
    store: AuthRateLimitStore,
    config: CommunityGuardrailConfig,
    *,
    user: AuthUser,
) -> tuple[CommunityGuardrailAgeDecision, AuthRateLimitDecision]:
    age = evaluate_account_age_guardrail(user=user, minimum_age_seconds=config.join_group_min_account_age_seconds)
    rate = store.check_scope_allowed(
        scope="study_group_join_user",
        raw_key=user.user_id,
        limit=config.join_group_max_actions_per_window,
        window_seconds=config.join_group_window_seconds,
    )
    return age, rate


def record_join_group(store: AuthRateLimitStore, config: CommunityGuardrailConfig, *, user: AuthUser) -> None:
    store.record_scope_action(
        scope="study_group_join_user",
        raw_key=user.user_id,
        window_seconds=config.join_group_window_seconds,
    )


def check_join_request_allowed(
    store: AuthRateLimitStore,
    config: CommunityGuardrailConfig,
    *,
    user: AuthUser,
) -> tuple[CommunityGuardrailAgeDecision, AuthRateLimitDecision]:
    age = evaluate_account_age_guardrail(user=user, minimum_age_seconds=config.join_request_min_account_age_seconds)
    rate = store.check_scope_allowed(
        scope="study_group_join_request_user",
        raw_key=user.user_id,
        limit=config.join_request_max_actions_per_window,
        window_seconds=config.join_request_window_seconds,
    )
    return age, rate


def record_join_request(store: AuthRateLimitStore, config: CommunityGuardrailConfig, *, user: AuthUser) -> None:
    store.record_scope_action(
        scope="study_group_join_request_user",
        raw_key=user.user_id,
        window_seconds=config.join_request_window_seconds,
    )


def check_post_allowed(
    store: AuthRateLimitStore,
    config: CommunityGuardrailConfig,
    *,
    user: AuthUser,
) -> tuple[CommunityGuardrailAgeDecision, AuthRateLimitDecision]:
    age = evaluate_account_age_guardrail(user=user, minimum_age_seconds=config.post_min_account_age_seconds)
    rate = store.check_scope_allowed(
        scope="study_group_post_user",
        raw_key=user.user_id,
        limit=config.post_max_actions_per_window,
        window_seconds=config.post_window_seconds,
    )
    return age, rate


def record_post(store: AuthRateLimitStore, config: CommunityGuardrailConfig, *, user: AuthUser) -> None:
    store.record_scope_action(
        scope="study_group_post_user",
        raw_key=user.user_id,
        window_seconds=config.post_window_seconds,
    )


def check_comment_allowed(
    store: AuthRateLimitStore,
    config: CommunityGuardrailConfig,
    *,
    user: AuthUser,
) -> tuple[CommunityGuardrailAgeDecision, AuthRateLimitDecision]:
    age = evaluate_account_age_guardrail(user=user, minimum_age_seconds=config.comment_min_account_age_seconds)
    rate = store.check_scope_allowed(
        scope="study_group_comment_user",
        raw_key=user.user_id,
        limit=config.comment_max_actions_per_window,
        window_seconds=config.comment_window_seconds,
    )
    return age, rate


def record_comment(store: AuthRateLimitStore, config: CommunityGuardrailConfig, *, user: AuthUser) -> None:
    store.record_scope_action(
        scope="study_group_comment_user",
        raw_key=user.user_id,
        window_seconds=config.comment_window_seconds,
    )
