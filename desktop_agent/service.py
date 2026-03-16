from __future__ import annotations

import time
from dataclasses import replace
from threading import Event
from typing import Callable

from desktop_agent.config_store import AgentConfig, ConfigStore
from desktop_agent.logging_utils import get_desktop_agent_logger
from desktop_agent.relay_client import DesktopAgentAuthExpired, RelayClient


ServiceStatusCallback = Callable[[str, str | None], None]


class DesktopAgentService:
    def __init__(
        self,
        config_store: ConfigStore | None = None,
        *,
        client_factory: Callable[[AgentConfig], RelayClient] = RelayClient,
        reconnect_delay_seconds: float = 10.0,  # 增加默认重连延迟到10秒
        refresh_interval_seconds: float = 6 * 60 * 60,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config_store = config_store or ConfigStore()
        self.client_factory = client_factory
        self.reconnect_delay_seconds = max(0.1, float(reconnect_delay_seconds))
        self.refresh_interval_seconds = max(60.0, float(refresh_interval_seconds))
        self.sleep_fn = sleep_fn
        self._logger = get_desktop_agent_logger("service")

    @staticmethod
    def _report_diagnostic(
        client: object,
        *,
        timeout_seconds: float = 1.0,
        **payload: object,
    ) -> None:
        async_reporter = getattr(client, "report_diagnostic_event_async", None)
        if callable(async_reporter):
            try:
                async_reporter(timeout_seconds=timeout_seconds, **payload)
                return
            except TypeError:
                async_reporter(**payload)
                return
            except Exception:
                return
        reporter = getattr(client, "report_diagnostic_event", None)
        if not callable(reporter):
            return
        try:
            reporter(timeout_seconds=timeout_seconds, **payload)
        except TypeError:
            try:
                reporter(**payload)
            except Exception:
                return
        except Exception:
            return

    @staticmethod
    def _emit_status(status_callback: ServiceStatusCallback | None, state: str, message: str | None = None) -> None:
        if status_callback is not None:
            status_callback(state, message)

    def _wait_or_stop(self, stop_event: Event | None, delay_seconds: float) -> bool:
        if stop_event is None:
            self.sleep_fn(delay_seconds)
            return False
        return bool(stop_event.wait(delay_seconds))

    def refresh_tokens(self, config: AgentConfig) -> AgentConfig:
        self._logger.info("refresh_tokens agent_id=%s", config.agent_id)
        client = self.client_factory(config)
        data = client.refresh_tokens()
        refreshed_agent_id = str(data.get("agentId") or "")
        if refreshed_agent_id and refreshed_agent_id != config.agent_id:
            raise RuntimeError("desktop agent refresh returned a different agent id")
        refreshed = replace(
            config,
            agent_token=str(data["agentToken"]),
            refresh_token=str(data["refreshToken"]),
        )
        self.config_store.save(refreshed)
        self._logger.info("refresh_tokens_succeeded agent_id=%s", refreshed.agent_id)
        return refreshed

    def run_forever(
        self,
        *,
        stop_event: Event | None = None,
        status_callback: ServiceStatusCallback | None = None,
    ) -> None:
        self._logger.info("service_loop_started")
        self._emit_status(status_callback, "STARTING", None)
        active_config: AgentConfig | None = None
        active_client: RelayClient | None = None
        while True:
            if stop_event is not None and stop_event.is_set():
                self._logger.info("service_loop_stopped_by_event")
                self._emit_status(status_callback, "STOPPED", None)
                return
            try:
                if active_config is None or active_client is None:
                    active_config = self.config_store.load()
                    active_client = self.client_factory(active_config)
            except FileNotFoundError:
                self._logger.warning("service_config_missing")
                self._emit_status(status_callback, "CONFIG_MISSING", "desktop agent config file is missing")
                if self._wait_or_stop(stop_event, self.reconnect_delay_seconds):
                    self._emit_status(status_callback, "STOPPED", None)
                    return
                continue

            config = active_config
            client = active_client
            self._emit_status(status_callback, "CONNECTING", None)
            try:
                client.run_session(
                    max_runtime_seconds=self.refresh_interval_seconds,
                    stop_event=stop_event,
                    on_connected=lambda: self._emit_status(status_callback, "RUNNING", None),
                )
            except KeyboardInterrupt:
                raise
            except DesktopAgentAuthExpired as exc:
                self._logger.warning("service_auth_expired error=%s", exc)
                self._emit_status(status_callback, "AUTH_EXPIRED", str(exc))
                self._report_diagnostic(
                    client,
                    level="warning",
                    category="auth",
                    event_type="auth_expired",
                    message=str(exc),
                    details={"agentId": config.agent_id},
                    project_id=config.project_id,
                )
                try:
                    self._emit_status(status_callback, "REFRESHING", None)
                    active_config = self.refresh_tokens(config)
                    active_client = self.client_factory(active_config)
                except KeyboardInterrupt:
                    raise
                except Exception as refresh_exc:
                    self._logger.exception("service_refresh_failed")
                    self._emit_status(status_callback, "ERROR", str(refresh_exc))
                    self._report_diagnostic(
                        client,
                        level="error",
                        category="auth",
                        event_type="refresh_failed",
                        message=str(refresh_exc),
                        details={"agentId": config.agent_id},
                        project_id=config.project_id,
                    )
                    if self._wait_or_stop(stop_event, self.reconnect_delay_seconds):
                        self._emit_status(status_callback, "STOPPED", None)
                        return
                continue
            except Exception as exc:
                self._logger.exception("service_session_failed")
                self._emit_status(status_callback, "ERROR", str(exc))
                self._report_diagnostic(
                    client,
                    level="error",
                    category="service",
                    event_type="session_failed",
                    message=str(exc),
                    details={"agentId": config.agent_id},
                    project_id=config.project_id,
                )
                if self._wait_or_stop(stop_event, self.reconnect_delay_seconds):
                    self._emit_status(status_callback, "STOPPED", None)
                    return
                continue

            if stop_event is not None and stop_event.is_set():
                self._logger.info("service_loop_stopped_after_session")
                self._emit_status(status_callback, "STOPPED", None)
                return
            try:
                self._emit_status(status_callback, "REFRESHING", None)
                active_config = self.refresh_tokens(config)
                active_client = self.client_factory(active_config)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                self._logger.exception("service_post_session_refresh_failed")
                self._emit_status(status_callback, "ERROR", str(exc))
                self._report_diagnostic(
                    client,
                    level="error",
                    category="auth",
                    event_type="post_session_refresh_failed",
                    message=str(exc),
                    details={"agentId": config.agent_id},
                    project_id=config.project_id,
                )
                if self._wait_or_stop(stop_event, self.reconnect_delay_seconds):
                    self._emit_status(status_callback, "STOPPED", None)
                    return
