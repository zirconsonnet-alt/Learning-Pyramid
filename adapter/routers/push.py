from fastapi import APIRouter, Depends, Query

from adapter.deps import get_api
from adapter.mappers import review_recommendation_page_to_dto
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from backend.system.api import SystemAPI


router = APIRouter()

@router.get("/subjects/{subjectId}/projects/{projectId}/review-recommendations")
def list_review_recommendations(
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    page = api.list_review_recommendations(project.internal_project_id, offset=offset, limit=limit)  # type: ignore[arg-type]
    return {"ok": True, "data": review_recommendation_page_to_dto(page, public_project_id=project.project_id)}


@router.get("/subjects/{subjectId}/projects/{projectId}/push-candidates")
def get_push_candidates(
    maxResults: int = Query(50, ge=1),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    ids = api.get_push_candidates(project.internal_project_id, maxResults)  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}
