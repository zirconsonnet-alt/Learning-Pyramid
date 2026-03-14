from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


AUTOSTART_SCRIPT_NAME = "LearningPyramidDesktopAgent.vbs"


def _default_startup_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata).expanduser().resolve() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home().resolve() / ".config" / "autostart"


def current_agent_command(*args: str) -> list[str]:
    if bool(getattr(sys, "frozen", False)):
        return [str(Path(sys.executable).resolve()), *[str(item) for item in args]]
    return [sys.executable, str((Path(__file__).resolve().parent / "main.py").resolve()), *[str(item) for item in args]]


def current_agent_launch_command() -> list[str]:
    return current_agent_command("run")


class AutostartManager:
    def __init__(self, startup_dir: Path | str | None = None, *, script_name: str = AUTOSTART_SCRIPT_NAME) -> None:
        self.startup_dir = Path(startup_dir or _default_startup_dir()).resolve()
        self.script_name = str(script_name)

    @property
    def script_path(self) -> Path:
        return self.startup_dir / self.script_name

    def enable(self, command: Sequence[str] | None = None) -> Path:
        args = [str(item) for item in (command or current_agent_launch_command())]
        self.startup_dir.mkdir(parents=True, exist_ok=True)
        command_line = subprocess.list2cmdline(args)
        escaped_command_line = command_line.replace('"', '""')
        script = (
            'Set WshShell = CreateObject("WScript.Shell")\r\n'
            f'WshShell.Run "{escaped_command_line}", 0, False\r\n'
        )
        self.script_path.write_text(script, encoding="utf-8", newline="\r\n")
        return self.script_path

    def disable(self) -> None:
        if self.script_path.exists():
            self.script_path.unlink()

    def is_enabled(self) -> bool:
        return self.script_path.exists()
