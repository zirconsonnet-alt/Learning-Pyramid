from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.system.version import APP_VERSION
from desktop_agent.ui import _default_device_name, _default_server_url, _update_history_label


if TYPE_CHECKING:
    from desktop_agent.ui import DesktopAgentUiController


@dataclass(frozen=True)
class LauncherState:
    status_key: str
    status_badge: str
    title: str
    message: str
    server_url: str
    project_id: str
    root_label: str
    root_dir: str
    device_name: str
    app_version: str
    update_status: str
    update_history: str
    start_enabled: bool
    reconfigure_label: str


def build_launcher_state(controller: "DesktopAgentUiController") -> LauncherState:
    saved = controller.load_saved_config()
    update_status = "自动更新已开启" if controller.auto_update_enabled() else "自动更新已关闭"
    update_history = _update_history_label(controller.load_update_state())
    if saved is None:
        return LauncherState(
            status_key="unconfigured",
            status_badge="尚未接入",
            title="还没有保存的连接器",
            message="请先登录并完成一次接入。接入完成后，后续启动不需要重新登录。",
            server_url=_default_server_url(),
            project_id="-",
            root_label="-",
            root_dir="请选择一个本地目录并完成接入",
            device_name=_default_device_name(),
            app_version=APP_VERSION,
            update_status=update_status,
            update_history=update_history,
            start_enabled=False,
            reconfigure_label="登录并接入",
        )

    is_running = controller.is_tray_running()
    if is_running:
        status_key = "running"
        status_badge = "运行中"
        title = "连接器正在后台运行"
        message = "当前连接器已在后台运行。重新启动会通知现有托盘进程刷新。"
    else:
        status_key = "stopped"
        status_badge = "可启动"
        title = "已保存连接器"
        message = "已保存的连接器可以直接启动，无需重新登录。"

    return LauncherState(
        status_key=status_key,
        status_badge=status_badge,
        title=title,
        message=message,
        server_url=saved.server_url,
        project_id=saved.project_id,
        root_label=saved.source_root_label or "默认根目录",
        root_dir=saved.root_dir,
        device_name=saved.device_name,
        app_version=saved.app_version,
        update_status=update_status,
        update_history=update_history,
        start_enabled=True,
        reconfigure_label="更换账号或重新接入",
    )
