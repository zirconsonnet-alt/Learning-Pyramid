from fastapi import APIRouter, Depends, Query

from adapter.deps import get_api
from adapter.mappers import review_recommendation_page_to_dto
from backend.system.api import SystemAPI


router = APIRouter()

@router.get("/projects/{projectId}/review-recommendations")
def list_review_recommendations(
    projectId: str,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1),
    api: SystemAPI = Depends(get_api),
) -> dict:
    page = api.list_review_recommendations(projectId, offset=offset, limit=limit)  # type: ignore[arg-type]
    return {"ok": True, "data": review_recommendation_page_to_dto(page)}


@router.get("/projects/{projectId}/push-candidates")
def get_push_candidates(
    projectId: str,
    maxResults: int = Query(50, ge=1),
    api: SystemAPI = Depends(get_api),
) -> dict:
    ids = api.get_push_candidates(projectId, maxResults)  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}
