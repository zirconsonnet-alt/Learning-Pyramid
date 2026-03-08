from __future__ import annotations

import mimetypes
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from adapter.deps import get_api
from backend.models.enums import InstancePresence, SessionMode
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.material_paths import resolve_material_file_path


router = APIRouter()


@router.get("/projects/{projectId}/media/instances/{instanceId}")
def stream_instance_media(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    s = api.begin_session(projectId, SessionMode.READ_ONLY)  # type: ignore[arg-type]
    try:
        storage_cfg = api.sys.project_storage_config_repo.get(s)
    finally:
        api.sys.rollback(s)

    p = resolve_material_file_path(storage_cfg, inst.material_id)

    if not p.exists():
        raise PreconditionFailure(f"material file not found: {p}")
    if not p.is_file():
        raise PreconditionFailure(f"material is not a file: {p}")

    media_type, _ = mimetypes.guess_type(str(p))
    return FileResponse(path=str(p), media_type=media_type or "application/octet-stream", filename=p.name)
