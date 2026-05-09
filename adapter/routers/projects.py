from fastapi import APIRouter, Depends, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import (
    audit_log_event_to_dto,
    project_config_to_dto,
    project_material_source_binding_to_dto,
    project_storage_config_to_dto,
    project_to_dto,
    study_material_to_dto,
    subject_context_to_dto,
    subject_to_dto,
    with_project_reference,
)
from adapter.schemas import (
    CreateProjectRequest,
    CreateStudyMaterialRequest,
    CreateSubjectRequest,
    EditStudyMaterialRequest,
    EditSubjectRequest,
    EditProjectRequest,
    SetProjectRollUpStrategyRequest,
    SetReviewRecommendationConfigRequest,
    SetProjectMaterialSourceBindingRequest,
)
from backend.models.enums import MaterialSourceKind, ProjectType, RollUpStrategy
from backend.models.errors import NotFound, PreconditionFailure
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


def _ensure_auth_project_access(project_id: str, request: Request, auth_store: AuthStore) -> None:
    if not current_runtime_features().auth_enabled:
        return
    user = require_request_auth_user(request)
    if str(project_id) not in set(auth_store.list_project_ids_for_user(user.user_id)):
        raise PreconditionFailure("project is not accessible for current user")


def _ensure_auth_material_project_ownership(request: Request, auth_store: AuthStore, materials: list | tuple) -> None:
    if not current_runtime_features().auth_enabled:
        return
    user = require_request_auth_user(request)
    allowed = set(auth_store.list_project_ids_for_user(user.user_id))
    for item in materials:
        project_id = getattr(item, "internal_project_key", None) or getattr(item, "project_id", None)
        if project_id is None:
            continue
        normalized_project_id = str(project_id)
        if normalized_project_id in allowed:
            continue
        auth_store.add_project_owner(normalized_project_id, user.user_id)
        allowed.add(normalized_project_id)


def _load_authorized_subject_context(
    project_id: str,
    request: Request,
    api: SystemAPI,
    auth_store: AuthStore,
) -> dict:
    if not current_runtime_features().auth_enabled:
        return api.get_subject_context(project_id)  # type: ignore[arg-type]

    user = require_request_auth_user(request)
    allowed = set(auth_store.list_project_ids_for_user(user.user_id))
    if str(project_id) in allowed:
        payload = api.get_subject_context(project_id)  # type: ignore[arg-type]
        _ensure_auth_material_project_ownership(request, auth_store, tuple(payload["materials"]))
        return payload

    try:
        payload = api.get_subject_context(project_id)  # type: ignore[arg-type]
    except NotFound as exc:
        raise PreconditionFailure("project is not accessible for current user") from exc

    subject_id = str(getattr(payload["subject"], "project_id"))
    if subject_id not in allowed:
        raise PreconditionFailure("project is not accessible for current user")

    auth_store.add_project_owner(project_id, user.user_id)
    _ensure_auth_material_project_ownership(request, auth_store, tuple(payload["materials"]))
    return payload


def _legacy_project_route_disabled() -> None:
    raise PreconditionFailure("旧项目链接已失效，请从学科中心重新进入项目")


def _current_scoped_project_ref(request: Request) -> tuple[str, str] | None:
    subject_id = getattr(request.state, "scoped_subject_id", None)
    project_id = getattr(request.state, "scoped_project_id", None)
    if subject_id is None or project_id is None:
        return None
    return str(subject_id), str(project_id)


def _resolve_scoped_project_id(subject_id: str, project_id: str, api: SystemAPI) -> str:
    return str(api.resolve_scoped_project_internal_key(subject_id, project_id))  # type: ignore[arg-type]


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


@router.get("/projects")
def list_projects(request: Request, api: SystemAPI = Depends(get_api), auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    items = _filter_auth_visible_projects(request, auth_store, list(api.list_projects()))
    items = [project_to_dto(p) for p in items]
    return {"ok": True, "data": items}


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
        _ensure_auth_material_project_ownership(request, auth_store, api.list_subject_materials(pid))
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
    _ensure_auth_material_project_ownership(request, auth_store, items)
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
    _ensure_auth_material_project_ownership(request, auth_store, (item,))
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
        item.internal_project_key or item.project_id
        for item in api.list_subject_materials(subjectId)  # type: ignore[arg-type]
        if item.material_id == materialId
        and item.project_id is not None
        and str(item.project_id) != str(subjectId)
    ]
    api.delete_subject_material(subjectId, materialId)  # type: ignore[arg-type]
    if current_runtime_features().auth_enabled:
        for related_project_id in cleanup_ids:
            auth_store.remove_project_memberships(related_project_id)
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/subject-context")
def get_project_subject_context(
    projectId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    scoped_ref = _current_scoped_project_ref(request)
    if scoped_ref is None:
        _legacy_project_route_disabled()
    payload = _load_authorized_subject_context(projectId, request, api, auth_store)
    payload["current_project_id"] = scoped_ref[1]
    return {"ok": True, "data": subject_context_to_dto(payload)}


@router.get("/subjects/{subjectId}/projects/{projectId}/subject-context")
def get_scoped_project_subject_context(
    subjectId: str,
    projectId: str,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ensure_auth_subject_access(subjectId, request, auth_store)
    payload = api.get_scoped_subject_context(subjectId, projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": subject_context_to_dto(payload)}


@router.post("/projects")
def create_project(
    req: CreateProjectRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _legacy_project_route_disabled()


@router.get("/subjects/{subjectId}/projects/{projectId}/project-config")
def get_scoped_project_config(subjectId: str, projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    internal_project_id = _resolve_scoped_project_id(subjectId, projectId, api)
    cfg = api.get_project_config(internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": with_project_reference(project_config_to_dto(cfg), subject_id=subjectId, project_id=projectId)}


@router.delete("/projects/{projectId}")
def delete_project(projectId: str, api: SystemAPI = Depends(get_api), auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    _legacy_project_route_disabled()


@router.patch("/projects/{projectId}")
def edit_project(projectId: str, req: EditProjectRequest, api: SystemAPI = Depends(get_api)) -> dict:
    _legacy_project_route_disabled()


@router.get("/projects/{projectId}/project-config")
def get_project_config(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_config(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_config_to_dto(cfg)}


@router.post("/projects/{projectId}/roll-up-strategy")
def set_project_roll_up_strategy(
    projectId: str,
    req: SetProjectRollUpStrategyRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_project_roll_up_strategy(projectId, _parse_roll_up_strategy(req.rollUpStrategy))  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.post("/projects/{projectId}/review-recommendation-config")
def set_review_recommendation_config(
    projectId: str,
    req: SetReviewRecommendationConfigRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_review_recommendation_config(  # type: ignore[arg-type]
        projectId,
        min_recall_points_to_enable=req.minRecallPointsToEnable,
        max_history_len=req.maxHistoryLen,
        recommended_batch_size=req.recommendedBatchSize,
        forgetting_curve_decay_per_day=req.forgettingCurveDecayPerDay,
    )
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/project-storage-config")
def get_project_storage_config(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_storage_config(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_storage_config_to_dto(cfg)}


@router.get("/projects/{projectId}/material-source-binding")
def get_project_material_source_binding(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_material_source_binding_to_dto(binding)}


@router.post("/projects/{projectId}/material-source-binding")
def set_project_material_source_binding(
    projectId: str,
    req: SetProjectMaterialSourceBindingRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_project_material_source_binding(  # type: ignore[arg-type]
        projectId,
        source_kind=_parse_material_source_kind(req.sourceKind),
        source_root_label=req.sourceRootLabel,
    )
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/audit-log-events")
def list_audit_log_events(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [audit_log_event_to_dto(ev) for ev in api.list_audit_log_events(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}
