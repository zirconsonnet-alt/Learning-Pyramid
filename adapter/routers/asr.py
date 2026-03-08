from __future__ import annotations

from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import asr_artifact_to_dto
from adapter.schemas import RequestAsrRequest
from backend.system.api import SystemAPI


router = APIRouter()


@router.post("/projects/{projectId}/asr")
def request_asr(projectId: str, req: RequestAsrRequest, api: SystemAPI = Depends(get_api)) -> dict:
    provider = req.provider or "WHISPER"
    aid = api.request_asr(  # type: ignore[arg-type]
        projectId,
        req.recallPointId,
        req.centerMs,
        req.preMs,
        req.postMs,
        provider,
    )
    return {"ok": True, "data": {"asrArtifactId": str(aid)}}


@router.get("/projects/{projectId}/asr-artifacts/{asrArtifactId}")
def get_asr_artifact(projectId: str, asrArtifactId: str, api: SystemAPI = Depends(get_api)) -> dict:
    art = api.get_asr_artifact(projectId, asrArtifactId)  # type: ignore[arg-type]
    return {"ok": True, "data": asr_artifact_to_dto(art)}
