from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from adapter.deps import get_api
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/projects/{projectId}/push-candidates")
def get_push_candidates(
    projectId: str,
    maxResults: int = Query(50, ge=1),
    api: SystemAPI = Depends(get_api),
) -> dict:
    ids = api.get_push_candidates(projectId, maxResults)  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}

