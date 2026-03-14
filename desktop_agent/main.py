from __future__ import annotations

import argparse
import os
import socket
from pathlib import Path

import requests

from backend.system.version import APP_VERSION
from desktop_agent.config_store import AgentConfig, ConfigStore
from desktop_agent.logging_utils import configure_desktop_agent_logging, get_desktop_agent_logger
from desktop_agent.relay_client import RelayClient
from desktop_agent.runtime_defaults import current_default_server_url
from desktop_agent.service import DesktopAgentService
from desktop_agent.tray import launch_tray
from desktop_agent.ui import launch_ui


def _default_server_url() -> str:
    return current_default_server_url().rstrip("/")


def _default_device_name() -> str:
    return socket.gethostname() or "WINDOWS-PC"


def _pair(args: argparse.Namespace) -> int:
    server_url = str(args.server_url).rstrip("/")
    root_dir = str(Path(args.root_dir).expanduser().resolve())
    pair_response = requests.post(
        f"{server_url}/api/desktop-agents/pair",
        json={
            "pairingCode": args.pairing_code,
            "deviceName": args.device_name,
            "platform": "windows",
            "appVersion": args.app_version,
        },
        timeout=30,
    )
    pair_response.raise_for_status()
    data = pair_response.json()["data"]
    config = AgentConfig(
        server_url=server_url,
        agent_id=str(data["agentId"]),
        agent_token=str(data["agentToken"]),
        refresh_token=str(data["refreshToken"]),
        project_id=str(args.project_id),
        root_dir=root_dir,
        device_name=str(args.device_name),
        app_version=str(args.app_version),
        source_root_label=str(args.source_root_label or Path(root_dir).name or "Desktop Media"),
    )
    ConfigStore().save(config)
    print(f"paired agent_id={config.agent_id}")
    print(f"config={ConfigStore().path}")
    return 0


def _sync(_: argparse.Namespace) -> int:
    store = ConfigStore()
    config = store.ensure_app_version() or store.load()
    client = RelayClient(config)
    report = client.sync_manifest()
    print(report)
    return 0


def _run(args: argparse.Namespace) -> int:
    store = ConfigStore()
    store.ensure_app_version()
    service = DesktopAgentService(
        store,
        reconnect_delay_seconds=float(args.reconnect_delay_seconds),
        refresh_interval_seconds=float(args.refresh_interval_seconds),
    )
    service.run_forever()
    return 0


def _ui(_: argparse.Namespace) -> int:
    return int(launch_ui())


def _tray(_: argparse.Namespace) -> int:
    return int(launch_tray())


def _healthcheck(_: argparse.Namespace) -> int:
    store = ConfigStore()
    store.base_dir.mkdir(parents=True, exist_ok=True)
    if store.exists():
        store.ensure_app_version()
    print(f"ok version={APP_VERSION}")
    return 0


def main() -> int:
    configure_desktop_agent_logging()
    logger = get_desktop_agent_logger("main")
    parser = argparse.ArgumentParser(prog="desktop-agent")
    parser.set_defaults(func=_ui)
    subparsers = parser.add_subparsers(dest="command")

    pair_parser = subparsers.add_parser("pair")
    pair_parser.add_argument("--server-url", default=_default_server_url())
    pair_parser.add_argument("--pairing-code", required=True)
    pair_parser.add_argument("--project-id", required=True)
    pair_parser.add_argument("--root-dir", required=True)
    pair_parser.add_argument("--device-name", default=_default_device_name())
    pair_parser.add_argument("--app-version", default=APP_VERSION)
    pair_parser.add_argument("--source-root-label")
    pair_parser.set_defaults(func=_pair)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.set_defaults(func=_sync)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--reconnect-delay-seconds", type=float, default=3.0)
    run_parser.add_argument("--refresh-interval-seconds", type=float, default=6 * 60 * 60)
    run_parser.set_defaults(func=_run)

    ui_parser = subparsers.add_parser("ui")
    ui_parser.set_defaults(func=_ui)

    tray_parser = subparsers.add_parser("tray")
    tray_parser.set_defaults(func=_tray)

    healthcheck_parser = subparsers.add_parser("healthcheck")
    healthcheck_parser.set_defaults(func=_healthcheck)

    argv = list(os.sys.argv[1:])
    args = parser.parse_args(argv)
    logger.info("desktop_agent_command command=%s argv=%s", getattr(args, "command", None), " ".join(argv))
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
