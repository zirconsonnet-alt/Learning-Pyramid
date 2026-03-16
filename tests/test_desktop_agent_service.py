from __future__ import annotations

from pathlib import Path

import pytest

from desktop_agent.config_store import AgentConfig, ConfigStore
from desktop_agent.relay_client import DesktopAgentAuthExpired
from desktop_agent.service import DesktopAgentService


def _seed_config(tmp_path: Path) -> ConfigStore:
    store = ConfigStore(tmp_path)
    store.save(
        AgentConfig(
            server_url="http://127.0.0.1:8000",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(tmp_path),
            device_name="BYLOU-PC",
        )
    )
    return store


def test_desktop_agent_service_refreshes_tokens_after_auth_expiry(tmp_path: Path) -> None:
    store = _seed_config(tmp_path)

    class StubClient:
        run_calls: list[tuple[str, float | None]] = []
        refresh_calls: list[str] = []

        def __init__(self, config: AgentConfig) -> None:
            self.config = config

        def refresh_tokens(self) -> dict[str, str]:
            StubClient.refresh_calls.append(self.config.refresh_token)
            return {
                "agentId": self.config.agent_id,
                "agentToken": "agent-token-2",
                "refreshToken": "refresh-token-2",
            }

        def run_session(
            self,
            *,
            max_runtime_seconds: float | None = None,
            stop_event=None,
            on_connected=None,
        ) -> None:
            StubClient.run_calls.append((self.config.agent_token, max_runtime_seconds))
            if len(StubClient.run_calls) == 1:
                raise DesktopAgentAuthExpired("desktop agent authentication expired")
            if on_connected is not None:
                on_connected()
            raise KeyboardInterrupt()

    service = DesktopAgentService(
        config_store=store,
        client_factory=StubClient,
        reconnect_delay_seconds=0.01,
        refresh_interval_seconds=120,
        sleep_fn=lambda _: None,
    )

    with pytest.raises(KeyboardInterrupt):
        service.run_forever()

    persisted = store.load()
    assert persisted.agent_token == "agent-token-2"
    assert persisted.refresh_token == "refresh-token-2"
    assert StubClient.refresh_calls == ["refresh-token-1"]
    assert StubClient.run_calls == [("agent-token-1", 120), ("agent-token-2", 120)]


def test_desktop_agent_service_refreshes_tokens_after_planned_session_rotation(tmp_path: Path) -> None:
    store = _seed_config(tmp_path)

    class StubClient:
        run_calls: list[tuple[str, float | None]] = []
        refresh_calls: list[str] = []

        def __init__(self, config: AgentConfig) -> None:
            self.config = config

        def refresh_tokens(self) -> dict[str, str]:
            StubClient.refresh_calls.append(self.config.refresh_token)
            return {
                "agentId": self.config.agent_id,
                "agentToken": "agent-token-2",
                "refreshToken": "refresh-token-2",
            }

        def run_session(
            self,
            *,
            max_runtime_seconds: float | None = None,
            stop_event=None,
            on_connected=None,
        ) -> None:
            StubClient.run_calls.append((self.config.agent_token, max_runtime_seconds))
            if len(StubClient.run_calls) == 1:
                if on_connected is not None:
                    on_connected()
                return
            if on_connected is not None:
                on_connected()
            raise KeyboardInterrupt()

    service = DesktopAgentService(
        config_store=store,
        client_factory=StubClient,
        reconnect_delay_seconds=0.01,
        refresh_interval_seconds=180,
        sleep_fn=lambda _: None,
    )

    with pytest.raises(KeyboardInterrupt):
        service.run_forever()

    persisted = store.load()
    assert persisted.agent_token == "agent-token-2"
    assert persisted.refresh_token == "refresh-token-2"
    assert StubClient.refresh_calls == ["refresh-token-1"]
    assert StubClient.run_calls == [("agent-token-1", 180), ("agent-token-2", 180)]


def test_desktop_agent_service_reuses_client_after_session_failure(tmp_path: Path) -> None:
    store = _seed_config(tmp_path)

    class StubClient:
        instances: list["StubClient"] = []
        run_calls: list[int] = []

        def __init__(self, config: AgentConfig) -> None:
            self.config = config
            self.run_count = 0
            StubClient.instances.append(self)

        def run_session(
            self,
            *,
            max_runtime_seconds: float | None = None,
            stop_event=None,
            on_connected=None,
        ) -> None:
            self.run_count += 1
            StubClient.run_calls.append(self.run_count)
            if self.run_count == 1:
                raise RuntimeError("temporary network failure")
            raise KeyboardInterrupt()

        def report_diagnostic_event_async(self, **kwargs) -> None:
            return None

    service = DesktopAgentService(
        config_store=store,
        client_factory=StubClient,
        reconnect_delay_seconds=0.01,
        refresh_interval_seconds=120,
        sleep_fn=lambda _: None,
    )

    with pytest.raises(KeyboardInterrupt):
        service.run_forever()

    assert len(StubClient.instances) == 1
    assert StubClient.instances[0].run_count == 2
    assert StubClient.run_calls == [1, 2]
