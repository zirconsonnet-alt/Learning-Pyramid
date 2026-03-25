from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from adapter.deps import get_api
from backend.system.api import SystemAPI


router = APIRouter()


def _review_recommendations_response(project_id: str, max_results: int, api: SystemAPI) -> dict:
    ids = api.list_review_recommendations(project_id, max_results)  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}


@router.get("/projects/{projectId}/review-recommendations")
def list_review_recommendations(
    projectId: str,
    maxResults: int = Query(50, ge=1),
    api: SystemAPI = Depends(get_api),
) -> dict:
    return _review_recommendations_response(projectId, maxResults, api)


@router.get("/projects/{projectId}/push-candidates")
def get_push_candidates(
    projectId: str,
    maxResults: int = Query(50, ge=1),
    api: SystemAPI = Depends(get_api),
) -> dict:
    return _review_recommendations_response(projectId, maxResults, api)
