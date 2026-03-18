from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from adapter.deps import get_api
from backend.models.enums import InstancePresence, SessionMode
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.material_paths import resolve_material_file_path
from backend.system.runtime_features import require_server_media_stream_enabled


router = APIRouter()


@router.get("/projects/{projectId}/media/instances/{instanceId}")
def stream_instance_media(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    require_server_media_stream_enabled()
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    session = api.begin_session(projectId, SessionMode.READ_ONLY)  # type: ignore[arg-type]
    try:
        storage_cfg = api.sys.project_storage_config_repo.get(session)
    finally:
        api.sys.rollback(session)

    file_path = resolve_material_file_path(storage_cfg, inst.material_id)
    if not file_path.exists():
        raise PreconditionFailure(f"material file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"material is not a file: {file_path}")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=media_type or "application/octet-stream", filename=file_path.name)
