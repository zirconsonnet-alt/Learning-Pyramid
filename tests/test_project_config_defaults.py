from datetime import datetime, timezone

from backend.models.enums import ReviewChainTemplateItemKind, RollUpStrategy
from backend.models.project_config import default_project_config
from backend.models.types import ProjectId
from backend.system.auth_store import SQLiteAuthStore


def _template_signature(template):
    return tuple((item.kind, item.count) for item in template)


def test_default_project_config_uses_review_task_then_convergence_and_isomorphic_roll_up():
    config = default_project_config(
        project_id=ProjectId("proj_default"),
        updated_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
    )

    assert config.roll_up_strategy == RollUpStrategy.LEARNING_OBJECT_ISOMORPHIC
    assert _template_signature(config.layer_configs[0].review_chain_template) == (
        (ReviewChainTemplateItemKind.REVIEW_TASK, None),
        (ReviewChainTemplateItemKind.CONVERGENCE, None),
    )


def test_new_user_global_settings_default_review_template_is_review_task_then_convergence(tmp_path):
    auth_store = SQLiteAuthStore(tmp_path / "auth.sqlite3")
    user = auth_store.create_user("defaults@example.com", "password-123")

    settings = auth_store.get_user_global_settings(user.user_id)

    assert tuple((step.kind, step.count) for step in settings.default_project_review_template) == (
        ("REVIEW_TASK", None),
        ("CONVERGENCE", None),
    )


def test_new_user_global_settings_enable_random_micro_breaks_by_default(tmp_path):
    auth_store = SQLiteAuthStore(tmp_path / "auth.sqlite3")
    user = auth_store.create_user("micro-break-defaults@example.com", "password-123")

    settings = auth_store.get_user_global_settings(user.user_id)

    assert settings.pomodoro_micro_breaks.enabled is True
    assert settings.pomodoro_micro_breaks.min_interval_seconds == 180
    assert settings.pomodoro_micro_breaks.max_interval_seconds == 300
    assert settings.pomodoro_micro_breaks.duration_seconds == 10
