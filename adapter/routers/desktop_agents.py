from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from adapter.auth import require_request_auth_user
from adapter.desktop_agent_diagnostic_events import record_desktop_agent_diagnostic_event, utc_now_text
from adapter.desktop_agent_hls_job_audit import persist_runtime_hls_job_audit
from adapter.desktop_agent_setup import DesktopAgentSetupManager, collect_desktop_agent_setup_catalog
from adapter.deps import get_auth_store, get_desktop_agent_runtime, get_desktop_agent_setup_manager
from adapter.mappers import desktop_agent_to_dto
from adapter.schemas import (
    CompleteDesktopAgentAccountSetupRequest,
    CompleteDesktopAgentSetupRequest,
    DesktopAgentDiagnosticEventRequest,
    DesktopAgentHlsJobStateRequest,
    DesktopAgentManifestSyncRequest,
    PairDesktopAgentRequest,
    ProvisionDesktopAgentRequest,
    RefreshDesktopAgentTokenRequest,
)
from backend.models.enums import DesktopAgentStatus, MaterialSourceKind
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.hls_cache_entry import HlsCacheEntry
from backend.system.desktop_agent_setup_code import decode_desktop_agent_setup_code
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_media_hls import (
    hls_cache_ttl_seconds,
    invalidate_hls_cache_entries_for_instance,
    normalize_hls_artifact_path,
    prune_hls_cache,
    resolve_hls_artifact_disk_path,
    serialize_hls_profile,
)
from backend.system.desktop_agent_runtime import (
    DesktopAgentHlsJobNotFoundError,
    DesktopAgentProbeNotFoundError,
    DesktopAgentRuntime,
    DesktopAgentStreamClosedError,
    DesktopAgentStreamNotFoundError,
)
from backend.system.http_runtime_config import current_http_runtime_config
from adapter.deps import get_api


router = APIRouter()


def _public_server_url(request: Request) -> str:
    http_config = current_http_runtime_config()
    return str(http_config.public_origin or f"{request.base_url.scheme}://{request.base_url.netloc}").rstrip("/")


def _decode_setup_token(setup_code: str) -> str:
    return decode_desktop_agent_setup_code(setup_code).setup_token


def _bearer_token_from_http_request(request: Request) -> str:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Agent authentication required")
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Agent authentication required")
    return token


def _bearer_token_from_websocket(websocket: WebSocket) -> str:
    auth_header = str(websocket.headers.get("Authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    query_token = str(websocket.query_params.get("agentToken", "")).strip()
    if query_token:
        return query_token
    raise HTTPException(status_code=401, detail="Agent authentication required")


def _update_hls_job_state_from_agent(
    *,
    auth_store: AuthStore,
    runtime: DesktopAgentRuntime,
    agent,
    job_id: str,
    state: str,
    message: str | None = None,
):
    try:
        job = runtime.update_hls_job_state(
            str(job_id),
            agent_id=agent.agent_id,
            state=str(state),
            message=None if message is None else str(message),
        )
        persist_runtime_hls_job_audit(auth_store, job)
        if job.state in {"RUNNING", "COMPLETED", "FAILED", "CANCELLED"}:
            record_desktop_agent_diagnostic_event(
                auth_store,
                agent_id=agent.agent_id,
                user_id=agent.user_id,
                level="error" if job.state == "FAILED" else ("warning" if job.state == "CANCELLED" else "info"),
                category="hls",
                event_type=f"hls_job_{str(job.state).lower()}",
                message=str(job.message or f"HLS job {str(job.state).lower()}"),
                details={
                    "jobId": job.job_id,
                    "cacheKey": job.cache_key,
                    "artifactCount": int(job.artifact_count),
                    "artifactBytes": int(job.artifact_bytes),
                },
                project_id=job.project_id,
                instance_id=job.instance_id,
                relative_path=job.relative_path,
                created_at=job.updated_at,
            )
        return job
    except DesktopAgentHlsJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _manifest_entry_cache_changed(
    *,
    cached_probe,
    size_bytes: int | None,
    modified_at: str | None,
) -> bool:
    if modified_at is not None and str(cached_probe.modified_at or "").strip() != str(modified_at).strip():
        return True
    if size_bytes is not None and cached_probe.size_bytes != int(size_bytes):
        return True
    return False


@router.post("/desktop-agents/pairing-codes")
def create_desktop_agent_pairing_code(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
    return {
        "ok": True,
        "data": {
            "pairingCode": pairing.pairing_code,
            "expiresAt": pairing.expires_at,
        },
    }


@router.get("/desktop-agents")
def list_desktop_agents(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    items = [desktop_agent_to_dto(item) for item in auth_store.list_desktop_agents_for_user(user.user_id)]
    return {"ok": True, "data": items}


@router.post("/desktop-agents/pair")
def pair_desktop_agent(req: PairDesktopAgentRequest, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    agent, agent_token, refresh_token = auth_store.pair_desktop_agent(
        req.pairingCode,
        device_name=req.deviceName,
        platform=req.platform,
        app_version=req.appVersion,
    )
    return {
        "ok": True,
        "data": {
            "agentId": agent.agent_id,
            "agentToken": agent_token,
            "refreshToken": refresh_token,
            "serverTime": agent.paired_at,
        },
    }


@router.get("/desktop-agents/account-bootstrap")
def get_desktop_agent_account_bootstrap(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": {
            "serverUrl": _public_server_url(request),
            **collect_desktop_agent_setup_catalog(user.user_id, auth_store=auth_store, api=api),
        },
    }


@router.post("/desktop-agents/account-pair")
def provision_desktop_agent_for_logged_in_user(
    req: ProvisionDesktopAgentRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
    agent, agent_token, refresh_token = auth_store.pair_desktop_agent(
        pairing.pairing_code,
        device_name=req.deviceName,
        platform=req.platform,
        app_version=req.appVersion,
    )
    return {
        "ok": True,
        "data": {
            "agentId": agent.agent_id,
            "agentToken": agent_token,
            "refreshToken": refresh_token,
            "serverTime": agent.paired_at,
        },
    }


@router.post("/desktop-agents/account-complete")
def complete_logged_in_desktop_agent_setup(
    req: CompleteDesktopAgentAccountSetupRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    if not auth_store.user_has_desktop_agent(user.user_id, req.agentId):
        raise HTTPException(status_code=403, detail="Desktop agent access denied")
    if not auth_store.user_has_project_access(user.user_id, req.projectId):
        raise HTTPException(status_code=403, detail="Project access denied")
    normalized_label = None if req.sourceRootLabel is None else str(req.sourceRootLabel).strip() or None
    api.set_project_material_source_binding(  # type: ignore[arg-type]
        req.projectId,
        source_kind=MaterialSourceKind.DESKTOP_AGENT_MANIFEST,
        desktop_agent_id=req.agentId,
        source_root_label=normalized_label,
    )
    return {
        "ok": True,
        "data": {
            "projectId": str(req.projectId),
            "agentId": str(req.agentId),
            "sourceRootLabel": normalized_label,
        },
    }


@router.post("/desktop-agents/refresh-token")
def refresh_desktop_agent_token(req: RefreshDesktopAgentTokenRequest, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    try:
        agent, agent_token, refresh_token = auth_store.refresh_desktop_agent_tokens(req.refreshToken)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid desktop agent refresh token") from exc
    return {
        "ok": True,
        "data": {
            "agentId": agent.agent_id,
            "agentToken": agent_token,
            "refreshToken": refresh_token,
            "serverTime": utc_now_text(),
        },
    }


@router.post("/desktop-agents/manifest-sync")
def desktop_agent_manifest_sync(
    req: DesktopAgentManifestSyncRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    token = _bearer_token_from_http_request(request)
    try:
        agent = auth_store.get_desktop_agent_by_token(token)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid agent token") from exc
    if agent.agent_id != req.agentId:
        raise HTTPException(status_code=403, detail="Agent identity mismatch")

    binding = api.get_project_material_source_binding(req.projectId)  # type: ignore[arg-type]
    if binding.source_kind != MaterialSourceKind.DESKTOP_AGENT_MANIFEST:
        raise HTTPException(status_code=409, detail="Project is not bound to desktop agent manifest source")
    if binding.desktop_agent_id is None or str(binding.desktop_agent_id) != agent.agent_id:
        raise HTTPException(status_code=403, detail="Desktop agent is not bound to this project")

    manifest_entry_by_path = {
        str(entry.relativePath).strip(): {
            "sizeBytes": None if entry.sizeBytes is None else int(entry.sizeBytes),
            "modifiedAt": None if entry.modifiedAt is None else str(entry.modifiedAt).strip() or None,
        }
        for entry in req.entries
        if str(entry.relativePath).strip()
    }

    report = api.sync_learning_objects_from_manifest(  # type: ignore[arg-type]
        req.projectId,
        root_title=req.rootTitle,
        manifest_entries=tuple(
            {
                "relativePath": entry.relativePath,
                "displayName": entry.displayName,
                "mediaKind": entry.mediaKind,
                "sizeBytes": entry.sizeBytes,
                "modifiedAt": entry.modifiedAt,
            }
            for entry in req.entries
        ),
    )

    instances = api.list_instances(req.projectId)  # type: ignore[arg-type]
    instance_id_by_material = {inst.material_id.as_posix(): str(inst.instance_id) for inst in instances}
    hls_entries = auth_store.list_all_hls_cache_entries()
    hls_cached_instance_ids = {
        str(entry.instance_id)
        for entry in hls_entries
        if str(entry.project_id) == str(req.projectId) and str(entry.agent_id) == agent.agent_id
    }
    for relative_path, manifest_meta in manifest_entry_by_path.items():
        instance_id = instance_id_by_material.get(relative_path)
        if not instance_id:
            continue
        cached_probe = auth_store.get_desktop_media_probe_cache(req.projectId, instance_id, agent.agent_id)
        should_invalidate = False
        if cached_probe is not None:
            should_invalidate = _manifest_entry_cache_changed(
                cached_probe=cached_probe,
                size_bytes=manifest_meta["sizeBytes"],
                modified_at=manifest_meta["modifiedAt"],
            )
        elif instance_id in hls_cached_instance_ids and (
            manifest_meta["sizeBytes"] is not None or manifest_meta["modifiedAt"] is not None
        ):
            should_invalidate = True
        if not should_invalidate:
            continue
        auth_store.delete_desktop_media_probe_cache(req.projectId, instance_id, agent.agent_id)
        invalidate_hls_cache_entries_for_instance(
            auth_store,
            project_id=req.projectId,
            instance_id=instance_id,
            agent_id=agent.agent_id,
        )
        for job in runtime.list_hls_jobs(agent_id=agent.agent_id):
            if (
                str(job.project_id) != str(req.projectId)
                or str(job.instance_id) != instance_id
                or job.state in {"COMPLETED", "FAILED", "CANCELLED"}
            ):
                continue
            cancelled_job = runtime.cancel_hls_job(
                job.job_id,
                reason="desktop agent media changed during manifest sync",
                notify_agent=True,
            )
            persist_runtime_hls_job_audit(auth_store, cancelled_job)
    return {"ok": True, "data": report}


@router.post("/desktop-agents/diagnostic-events")
def create_desktop_agent_diagnostic_event(
    req: DesktopAgentDiagnosticEventRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    token = _bearer_token_from_http_request(request)
    try:
        agent = auth_store.get_desktop_agent_by_token(token)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid agent token") from exc
    project_id = None if req.projectId is None else str(req.projectId)
    if project_id is not None and not auth_store.user_has_project_access(agent.user_id, project_id):
        raise HTTPException(status_code=403, detail="Desktop agent project access denied")
    event = record_desktop_agent_diagnostic_event(
        auth_store,
        agent_id=agent.agent_id,
        user_id=agent.user_id,
        level=req.level,
        category=req.category,
        event_type=req.eventType,
        message=req.message,
        details={str(key): value for key, value in dict(req.details).items()},
        project_id=project_id,
        instance_id=None if req.instanceId is None else str(req.instanceId),
        relative_path=None if req.relativePath is None else str(req.relativePath),
        created_at=req.createdAt,
    )
    return {
        "ok": True,
        "data": {
            "eventId": event.event_id,
            "createdAt": event.created_at,
        },
    }


@router.put("/desktop-agents/hls-jobs/{jobId}/state")
def update_desktop_agent_hls_job_state(
    jobId: str,
    req: DesktopAgentHlsJobStateRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    token = _bearer_token_from_http_request(request)
    try:
        agent = auth_store.get_desktop_agent_by_token(token)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid agent token") from exc
    job = _update_hls_job_state_from_agent(
        auth_store=auth_store,
        runtime=runtime,
        agent=agent,
        job_id=jobId,
        state=req.state,
        message=req.message,
    )
    return {
        "ok": True,
        "data": {
            "jobId": job.job_id,
            "state": job.state,
            "updatedAt": job.updated_at,
        },
    }


@router.get("/desktop-agents/setup-bootstrap")
def get_desktop_agent_setup_bootstrap(
    setupCode: str,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
    setup_manager: DesktopAgentSetupManager = Depends(get_desktop_agent_setup_manager),
) -> dict:
    try:
        setup_token = _decode_setup_token(setupCode)
        data = setup_manager.bootstrap(setup_token, auth_store=auth_store, api=api)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Desktop agent setup session not found") from exc
    except PreconditionFailure as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "data": data}


@router.post("/desktop-agents/setup-complete")
def complete_desktop_agent_setup(
    req: CompleteDesktopAgentSetupRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
    setup_manager: DesktopAgentSetupManager = Depends(get_desktop_agent_setup_manager),
) -> dict:
    try:
        setup_token = _decode_setup_token(req.setupCode)
        data = setup_manager.finalize(
            setup_token,
            auth_store=auth_store,
            api=api,
            agent_id=req.agentId,
            project_id=req.projectId,
            source_root_label=req.sourceRootLabel,
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Desktop agent setup session not found") from exc
    except PreconditionFailure as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "data": data}


@router.websocket("/desktop-agents/ws")
async def desktop_agent_ws(websocket: WebSocket) -> None:
    auth_store = get_auth_store()
    runtime = get_desktop_agent_runtime()
    try:
        token = _bearer_token_from_websocket(websocket)
        agent = auth_store.get_desktop_agent_by_token(token)
    except (HTTPException, NotFound):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    runtime.register_connection(agent.agent_id, websocket)
    auth_store.update_desktop_agent_presence(agent.agent_id, status=DesktopAgentStatus.ONLINE)
    await websocket.send_json({"type": "connected", "agentId": agent.agent_id})

    try:
        while True:
            for command in runtime.drain_commands(agent.agent_id):
                await websocket.send_json(command)
            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=0.25)
            except TimeoutError:
                continue
            message_type = str(payload.get("type", "")).strip()
            if message_type == "hello":
                if str(payload.get("agentId", "")).strip() != agent.agent_id:
                    await websocket.close(code=1008)
                    return
                updated_agent = auth_store.update_desktop_agent_presence(
                    agent.agent_id,
                    status=DesktopAgentStatus.ONLINE,
                    device_name=None if payload.get("deviceName") is None else str(payload.get("deviceName")),
                    app_version=None if payload.get("appVersion") is None else str(payload.get("appVersion")),
                )
                await websocket.send_json(
                    {
                        "type": "hello.ack",
                        "agentId": updated_agent.agent_id,
                        "serverTime": updated_agent.last_seen_at,
                    }
                )
                continue
            if message_type == "heartbeat":
                updated_agent = auth_store.update_desktop_agent_presence(
                    agent.agent_id,
                    status=DesktopAgentStatus.ONLINE,
                )
                await websocket.send_json(
                    {
                        "type": "heartbeat.ack",
                        "agentId": updated_agent.agent_id,
                        "serverTime": updated_agent.last_seen_at,
                    }
                )
                continue
            if message_type == "probe.result":
                try:
                    runtime.resolve_probe_request(
                        str(payload.get("requestId", "")),
                        agent_id=agent.agent_id,
                        payload=payload,
                    )
                except DesktopAgentProbeNotFoundError:
                    await websocket.send_json({"type": "ignored", "reason": "probe_request_not_found"})
                    continue
                except PermissionError:
                    await websocket.close(code=1008)
                    return
                continue
            if message_type == "job.state":
                try:
                    _update_hls_job_state_from_agent(
                        auth_store=auth_store,
                        runtime=runtime,
                        agent=agent,
                        job_id=str(payload.get("jobId", "")),
                        state=str(payload.get("state", "")),
                        message=None if payload.get("message") is None else str(payload.get("message")),
                    )
                except HTTPException as exc:
                    if exc.status_code == 404:
                        # A late job.state update can arrive after the runtime has already
                        # discarded the terminal HLS job and a new viewer request has
                        # re-enqueued fresh work for the same cache key. Swallow this stale
                        # update instead of emitting an `ignored` frame that would race
                        # ahead of the new `hls.start` command on the agent websocket.
                        continue
                    await websocket.close(code=1008)
                    return
                continue
            await websocket.send_json({"type": "ignored", "reason": "unsupported_message"})
    except WebSocketDisconnect:
        pass
    finally:
        runtime.unregister_connection(agent.agent_id, websocket)
        for job in runtime.list_hls_jobs(agent_id=agent.agent_id):
            if job.state in {"FAILED", "CANCELLED"}:
                persist_runtime_hls_job_audit(auth_store, job)


@router.put("/desktop-agents/stream-sessions/{streamId}/chunks")
async def upload_stream_session_chunk(
    streamId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    token = _bearer_token_from_http_request(request)
    try:
        agent = auth_store.get_desktop_agent_by_token(token)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid agent token") from exc

    content = await request.body()
    content_type = str(request.headers.get("X-Content-Type", "")).strip() or "application/octet-stream"
    file_size_text = str(request.headers.get("X-File-Size", "")).strip()
    range_start_text = str(request.headers.get("X-Range-Start", "")).strip()
    range_end_text = str(request.headers.get("X-Range-End", "")).strip()
    is_final_text = str(request.headers.get("X-Is-Final", "")).strip().lower()
    try:
        runtime.append_stream_chunk(
            streamId,
            agent_id=agent.agent_id,
            content=content,
            content_type=content_type,
            file_size=None if not file_size_text else int(file_size_text),
            range_start=None if not range_start_text else int(range_start_text),
            range_end=None if not range_end_text else int(range_end_text),
            is_final=is_final_text not in {"0", "false", "no", "off"},
        )
    except DesktopAgentStreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DesktopAgentStreamClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        auth_store.add_media_stream_session_agent_bytes(streamId, len(content))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="media stream session not found in auth store") from exc
    return {"ok": True, "data": None}


@router.put("/desktop-agents/hls-jobs/{jobId}/artifacts/{artifactPath:path}")
async def upload_hls_job_artifact(
    jobId: str,
    artifactPath: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    token = _bearer_token_from_http_request(request)
    try:
        agent = auth_store.get_desktop_agent_by_token(token)
    except NotFound as exc:
        raise HTTPException(status_code=401, detail="Invalid agent token") from exc

    try:
        job = runtime.get_hls_job(jobId)
    except DesktopAgentHlsJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if job.agent_id != agent.agent_id:
        raise HTTPException(status_code=403, detail="HLS job agent mismatch")

    normalized_artifact_path = normalize_hls_artifact_path(artifactPath)
    content = await request.body()
    artifact_file = resolve_hls_artifact_disk_path(job.cache_key, normalized_artifact_path)
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_bytes(content)
    job = runtime.record_hls_job_artifact(jobId, size_bytes=len(content))

    existing_entry = auth_store.get_hls_cache_entry(job.cache_key, normalized_artifact_path)
    now_text = utc_now_text()
    expires_at = (
        datetime.fromisoformat(now_text) + timedelta(seconds=hls_cache_ttl_seconds())
    ).replace(microsecond=0).isoformat()
    auth_store.upsert_hls_cache_entry(
        HlsCacheEntry(
            cache_key=job.cache_key,
            project_id=job.project_id,
            instance_id=job.instance_id,
            agent_id=job.agent_id,
            profile=serialize_hls_profile(job.profile),
            segment_name=normalized_artifact_path,
            file_path=str(artifact_file),
            size_bytes=len(content),
            created_at=now_text if existing_entry is None else existing_entry.created_at,
            last_accessed_at=now_text,
            expires_at=expires_at,
        )
    )
    persist_runtime_hls_job_audit(auth_store, job, observed_at=now_text)
    if normalized_artifact_path.endswith(".m3u8"):
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            level="info",
            category="hls",
            event_type="hls_manifest_uploaded",
            message=f"Uploaded HLS manifest {normalized_artifact_path}",
            details={
                "jobId": job.job_id,
                "cacheKey": job.cache_key,
                "artifactPath": normalized_artifact_path,
                "sizeBytes": len(content),
            },
            project_id=job.project_id,
            instance_id=job.instance_id,
            relative_path=job.relative_path,
            created_at=now_text,
        )
    prune_hls_cache(auth_store)
    return {"ok": True, "data": None}
