import logging
from dataclasses import dataclass

from fastapi import Depends, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api
from adapter.deps import get_auth_store
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import current_runtime_features

logger = logging.getLogger("learningpyramid.scoped_project")


@dataclass(frozen=True)
class ScopedProject:
    subject_id: str
    scoped_project_id: str
    internal_project_id: str


def resolve_scoped_project(
    subjectId: str,
    scopedProjectId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> ScopedProject:
    if current_runtime_features().auth_enabled:
        user = require_request_auth_user(request)
        allowed = set(auth_store.list_project_ids_for_user(user.user_id))
        if str(subjectId) not in allowed:
            from backend.models.errors import PreconditionFailure

            raise PreconditionFailure("subject is not accessible for current user")

    state_subject_id = getattr(request.state, "scoped_subject_id", None)
    state_project_id = getattr(request.state, "scoped_project_id", None)
    state_internal_project_id = getattr(request.state, "internal_project_id", None)
    if state_subject_id == subjectId and state_project_id == scopedProjectId and state_internal_project_id:
        internal_project_id = str(state_internal_project_id)
        resolved_from_cache = True
    else:
        internal_project_id = str(api.resolve_scoped_project_internal_key(subjectId, scopedProjectId))  # type: ignore[arg-type]
        request.state.scoped_subject_id = subjectId
        request.state.scoped_project_id = scopedProjectId
        request.state.internal_project_id = internal_project_id
        resolved_from_cache = False
    logger.info(
        "scoped_project_resolved subjectId=%s scopedProjectId=%s internalProjectId=%s cache=%s",
        subjectId,
        scopedProjectId,
        internal_project_id,
        resolved_from_cache,
    )
    return ScopedProject(subject_id=subjectId, scoped_project_id=scopedProjectId, internal_project_id=internal_project_id)
