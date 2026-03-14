from __future__ import annotations

import importlib


def test_main_defaults_to_ui(monkeypatch) -> None:
    module = importlib.import_module("desktop_agent.main")
    monkeypatch.setattr(module, "configure_desktop_agent_logging", lambda: None)

    class _Logger:
        def info(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(module, "get_desktop_agent_logger", lambda name: _Logger())
    monkeypatch.setattr(module, "launch_ui", lambda: 17)
    monkeypatch.setattr(module, "launch_tray", lambda: 99)
    monkeypatch.setattr(module.os, "sys", type("_Sys", (), {"argv": ["desktop-agent"]})())

    assert module.main() == 17
