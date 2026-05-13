from fastapi import APIRouter, Depends, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import (
    audit_log_event_to_dto,
    project_config_to_dto,
    project_material_source_binding_to_dto,
    project_storage_config_to_dto,
    study_material_to_dto,
    subject_context_to_dto,
    subject_to_dto,
    with_project_reference,
)
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import (
    CreateStudyMaterialRequest,
    CreateSubjectRequest,
    EditStudyMaterialRequest,
    EditSubjectRequest,
    SetProjectRollUpStrategyRequest,
    SetReviewRecommendationConfigRequest,
    SetProjectMaterialSourceBindingRequest,
)
from backend.models.enums import MaterialSourceKind, ProjectType, RollUpStrategy
from backend.models.errors import PreconditionFailure
from backend.models.study_material import StudyMaterialType
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import current_runtime_features


router = APIRouter()


def _filter_auth_visible_projects(request: Request, auth_store: AuthStore, projects: list) -> list:
    if not current_runtime_features().auth_enabled:
        return projects
    user = require_request_auth_user(request)
    allowed = set(auth_store.list_project_ids_for_user(user.user_id))
    return [project for project in projects if str(project.project_id) in allowed]


def _ensure_auth_subject_access(subject_id: str, request: Request, auth_store: AuthStore) -> None:
    if not current_runtime_features().auth_enabled:
        return
    user = require_request_auth_user(request)
    if str(subject_id) not in set(auth_store.list_project_ids_for_user(user.user_id)):
        raise PreconditionFailure("subject is not accessible for current user")


def _parse_material_source_kind(raw: str | None) -> MaterialSourceKind:
    value = str(raw or MaterialSourceKind.SERVER_FS.value).strip()
    try:
        return MaterialSourceKind(value)
    except ValueError as exc:
        raise PreconditionFailure("sourceKind must be one of SERVER_FS, BROWSER_LOCAL, NATIVE_LOCAL, MANUAL") from exc


def _parse_project_type(raw: str | None) -> ProjectType:
    value = str(raw or ProjectType.COURSE.value).strip()
    try:
        return ProjectType(value)
    except ValueError as exc:
        raise PreconditionFailure("projectType must be one of COURSE, BOOK, LOOSE_POINTS") from exc


def _parse_roll_up_strategy(raw: str | None) -> RollUpStrategy:
    value = str(raw or RollUpStrategy.THRESHOLD_AUTO.value).strip()
    try:
        return RollUpStrategy(value)
    except ValueError as exc:
        raise PreconditionFailure("rollUpStrategy must be one of MANUAL, THRESHOLD_AUTO, LEARNING_OBJECT_ISOMORPHIC") from exc


def _parse_study_material_type(raw: str | None) -> StudyMaterialType:
    value = str(raw or StudyMaterialType.COURSE.value).strip()
    try:
        return StudyMaterialType(value)
    except ValueError as exc:
        raise PreconditionFailure("materialType must be one of COURSE, BOOK, LOOSE_POINTS") from exc


@router.get("/subjects")
def list_subjects(request: Request, api: SystemAPI = Depends(get_api), auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    items = _filter_auth_visible_projects(request, auth_store, list(api.list_subjects()))
    return {"ok": True, "data": [subject_to_dto(p) for p in items]}


@router.post("/subjects")
def create_subject(
    req: CreateSubjectRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    pid = api.create_subject(req.title)
    if current_runtime_features().auth_enabled:
        user = require_request_auth_user(request)
        auth_store.add_project_owner(pid, user.user_id)
    return {"ok": True, "data": {"subjectId": str(pid)}}


@router.patch("/subjects/{subjectId}")
def edit_subject(
    subjectId: str,
    req: EditSubjectRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    api.edit_subject(subjectId, req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.delete("/subjects/{subjectId}")
def delete_subject(
    subjectId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    related_project_ids = api.list_membership_cleanup_project_ids(subjectId)  # type: ignore[arg-type]
    api.delete_subject(subjectId)  # type: ignore[arg-type]
    if current_runtime_features().auth_enabled:
        for related_project_id in related_project_ids:
            auth_store.remove_project_memberships(related_project_id)
    return {"ok": True, "data": None}


@router.get("/subjects/{subjectId}/materials")
def list_subject_materials(
    subjectId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    items = api.list_subject_materials(subjectId)  # type: ignore[arg-type]
    return {"ok": True, "data": [study_material_to_dto(item) for item in items]}


@router.post("/subjects/{subjectId}/materials")
def create_subject_material(
    subjectId: str,
    req: CreateStudyMaterialRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    item = api.create_subject_material(  # type: ignore[arg-type]
        subjectId,
        material_type=_parse_study_material_type(req.materialType),
        title=req.title,
    )
    return {"ok": True, "data": study_material_to_dto(item)}


@router.patch("/subjects/{subjectId}/materials/{materialId}")
def edit_subject_material(
    subjectId: str,
    materialId: str,
    req: EditStudyMaterialRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    item = api.edit_subject_material(subjectId, materialId, title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": study_material_to_dto(item)}


@router.delete("/subjects/{subjectId}/materials/{materialId}")
def delete_subject_material(
    subjectId: str,
    materialId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    cleanup_ids = [
        item.internal_project_id or item.scoped_project_id
        for item in api.list_subject_materials(subjectId)  # type: ignore[arg-type]
        if item.material_id == materialId
        and item.scoped_project_id is not None
        and str(item.scoped_project_id) != str(subjectId)
    ]
    api.delete_subject_material(subjectId, materialId)  # type: ignore[arg-type]
    if current_runtime_features().auth_enabled:
        for related_project_id in cleanup_ids:
            auth_store.remove_project_memberships(related_project_id)
    return {"ok": True, "data": None}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/subject-context")
def get_scoped_project_subject_context(
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    payload = api.get_scoped_subject_context_for_project(project.internal_project_id, public_project_id=project.scoped_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": subject_context_to_dto(payload)}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/project-config")
def get_project_config(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_config(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": with_project_reference(project_config_to_dto(cfg), subject_id=project.subject_id, project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/roll-up-strategy")
def set_project_roll_up_strategy(
    req: SetProjectRollUpStrategyRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_project_roll_up_strategy(project.internal_project_id, _parse_roll_up_strategy(req.rollUpStrategy))  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/review-recommendation-config")
def set_review_recommendation_config(
    req: SetReviewRecommendationConfigRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_review_recommendation_config(  # type: ignore[arg-type]
        project.internal_project_id,
        min_recall_points_to_enable=req.minRecallPointsToEnable,
        max_history_len=req.maxHistoryLen,
        recommended_batch_size=req.recommendedBatchSize,
        forgetting_curve_decay_per_day=req.forgettingCurveDecayPerDay,
    )
    return {"ok": True, "data": None}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/project-storage-config")
def get_project_storage_config(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_storage_config(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": with_project_reference(project_storage_config_to_dto(cfg), subject_id=project.subject_id, project_id=project.scoped_project_id)}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/material-source-binding")
def get_project_material_source_binding(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    binding = api.get_project_material_source_binding(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": with_project_reference(project_material_source_binding_to_dto(binding), subject_id=project.subject_id, project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/material-source-binding")
def set_project_material_source_binding(
    req: SetProjectMaterialSourceBindingRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_project_material_source_binding(  # type: ignore[arg-type]
        project.internal_project_id,
        source_kind=_parse_material_source_kind(req.sourceKind),
        source_root_label=req.sourceRootLabel,
    )
    return {"ok": True, "data": None}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/audit-log-events")
def list_audit_log_events(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [audit_log_event_to_dto(ev, public_project_id=project.scoped_project_id) for ev in api.list_audit_log_events(project.internal_project_id)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}
