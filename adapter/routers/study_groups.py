from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from adapter.auth import require_request_auth_user, request_user_has_global_role
from adapter.deps import get_auth_store
from adapter.schemas import (
    CreateStudyGroupJoinRequest,
    CreateStudyGroupPostCommentRequest,
    CreateStudyGroupPostRequest,
    CreateStudyGroupRequest,
    InviteStudyGroupMemberRequest,
    ReviewStudyGroupJoinRequestRequest,
    UpdateStudyGroupMemberRoleRequest,
    UpdateStudyGroupRequest,
)
from backend.system.app_paths import default_data_dir
from backend.system.auth_store import AuthStore, StudyGroup, StudyGroupJoinRequest, StudyGroupMember, StudyGroupPost, StudyGroupPostComment

router = APIRouter()

_AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _group_avatar_dir() -> Path:
    path = default_data_dir() / "avatars" / "study-groups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _group_avatar_path_for_key(avatar_key: str) -> Path:
    return _group_avatar_dir() / avatar_key


def _avatar_url_for_user(user_id: str, avatar_key: str | None) -> str | None:
    if not avatar_key:
        return None
    return f"/api/profile/avatar/{user_id}"


def _avatar_url_for_group(group: StudyGroup) -> str | None:
    if not group.avatar_key:
        return None
    return f"/api/study-groups/{group.group_id}/avatar?v={group.updated_at}"


def _group_to_dto(group: StudyGroup) -> dict[str, object]:
    return {
        "groupId": group.group_id,
        "name": group.name,
        "description": group.description,
        "visibility": group.visibility,
        "joinPolicy": group.join_policy,
        "status": group.status,
        "ownerUserId": group.owner_user_id,
        "ownerPublicUid": group.owner_public_uid,
        "ownerNickname": group.owner_nickname,
        "avatarUrl": _avatar_url_for_group(group),
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
        "memberCount": group.member_count,
        "memberRole": group.member_role,
        "joinRequestStatus": group.join_request_status,
    }


def _member_to_dto(member: StudyGroupMember) -> dict[str, object]:
    return {
        "userId": member.user_id,
        "publicUid": member.public_uid,
        "nickname": member.nickname,
        "avatarUrl": _avatar_url_for_user(member.user_id, member.avatar_key),
        "role": member.role,
        "joinedAt": member.joined_at,
    }


def _post_to_dto(post: StudyGroupPost) -> dict[str, object]:
    return {
        "postId": post.post_id,
        "groupId": post.group_id,
        "authorUserId": post.author_user_id,
        "authorPublicUid": post.author_public_uid,
        "authorNickname": post.author_nickname,
        "authorAvatarUrl": _avatar_url_for_user(post.author_user_id, post.author_avatar_key),
        "kind": post.kind,
        "content": post.content,
        "createdAt": post.created_at,
        "updatedAt": post.updated_at,
    }


def _post_comment_to_dto(comment: StudyGroupPostComment) -> dict[str, object]:
    return {
        "commentId": comment.comment_id,
        "groupId": comment.group_id,
        "postId": comment.post_id,
        "authorUserId": comment.author_user_id,
        "authorPublicUid": comment.author_public_uid,
        "authorNickname": comment.author_nickname,
        "authorAvatarUrl": _avatar_url_for_user(comment.author_user_id, comment.author_avatar_key),
        "content": comment.content,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
    }


def _join_request_to_dto(item: StudyGroupJoinRequest) -> dict[str, object]:
    return {
        "requestId": item.request_id,
        "groupId": item.group_id,
        "requesterUserId": item.requester_user_id,
        "requesterPublicUid": item.requester_public_uid,
        "requesterNickname": item.requester_nickname,
        "requesterAvatarUrl": _avatar_url_for_user(item.requester_user_id, item.requester_avatar_key),
        "message": item.message,
        "status": item.status,
        "createdAt": item.created_at,
        "reviewedAt": item.reviewed_at,
        "reviewedByUserId": item.reviewed_by_user_id,
    }


def _can_view_group(group: StudyGroup, *, is_admin: bool) -> bool:
    if is_admin:
        return True
    if group.status == "dissolved":
        return False
    if group.member_role is not None:
        return True
    return group.visibility == "public"


def _can_manage_group(group: StudyGroup, *, is_admin: bool) -> bool:
    if is_admin:
        return True
    return group.member_role in {"owner", "admin"}


def _can_manage_group_members(group: StudyGroup, *, is_admin: bool) -> bool:
    if is_admin:
        return True
    return group.member_role == "owner"


def _require_visible_group(request: Request, auth_store: AuthStore, group_id: str) -> tuple[StudyGroup, bool]:
    user = require_request_auth_user(request)
    is_admin = request_user_has_global_role(request, auth_store, ("super_admin", "admin"))
    group = auth_store.get_study_group(group_id, viewer_user_id=user.user_id)
    if not _can_view_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group access denied")
    return group, is_admin


@router.get("/study-groups")
def list_study_groups(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    groups = auth_store.list_study_groups_for_user(user.user_id)
    return {"ok": True, "data": [_group_to_dto(group) for group in groups]}


@router.post("/study-groups")
def create_study_group(
    req: CreateStudyGroupRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group = auth_store.create_study_group(
        owner_user_id=user.user_id,
        name=req.name,
        description=req.description,
        visibility=req.visibility,
        join_policy=req.joinPolicy,
    )
    return {"ok": True, "data": _group_to_dto(group)}


@router.get("/study-groups/{groupId}")
def get_study_group(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    group, _ = _require_visible_group(request, auth_store, groupId)
    return {"ok": True, "data": _group_to_dto(group)}


@router.get("/study-groups/{groupId}/avatar")
def get_study_group_avatar(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)):
    group, _ = _require_visible_group(request, auth_store, groupId)
    if not group.avatar_key:
        raise HTTPException(status_code=404, detail="Avatar not found")
    path = _group_avatar_path_for_key(group.avatar_key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(str(path))


@router.patch("/study-groups/{groupId}")
def update_study_group(
    groupId: str,
    req: UpdateStudyGroupRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group management denied")
    updated = auth_store.update_study_group(
        groupId,
        name=req.name,
        description=req.description,
        visibility=req.visibility,
        join_policy=req.joinPolicy,
    )
    viewer = require_request_auth_user(request)
    refreshed = auth_store.get_study_group(updated.group_id, viewer_user_id=viewer.user_id)
    return {"ok": True, "data": _group_to_dto(refreshed)}


@router.put("/study-groups/{groupId}/avatar")
async def upload_study_group_avatar(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group management denied")
    content_type = str(request.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
    suffix = _AVATAR_CONTENT_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=400, detail="Only jpeg, png, and webp avatars are supported")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Avatar payload is empty")
    if len(body) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar must be 2 MB or smaller")

    for candidate in _group_avatar_dir().glob(f"{group.group_id}.*"):
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
    avatar_key = f"{group.group_id}{suffix}"
    _group_avatar_path_for_key(avatar_key).write_bytes(body)
    updated = auth_store.update_study_group_avatar(group.group_id, avatar_key=avatar_key)
    refreshed = auth_store.get_study_group(updated.group_id, viewer_user_id=user.user_id)
    return {"ok": True, "data": _group_to_dto(refreshed)}


@router.post("/study-groups/{groupId}/join")
def join_study_group(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    group = auth_store.get_study_group(groupId, viewer_user_id=user.user_id)
    is_admin = request_user_has_global_role(request, auth_store, ("super_admin", "admin"))
    if group.member_role is None and not is_admin and group.visibility != "public":
        raise HTTPException(status_code=403, detail="Private study groups do not allow direct join")
    joined = auth_store.join_study_group(groupId, user_id=user.user_id)
    return {"ok": True, "data": _group_to_dto(joined)}


@router.post("/study-groups/{groupId}/leave")
def leave_study_group(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    _require_visible_group(request, auth_store, groupId)
    auth_store.leave_study_group(groupId, user_id=user.user_id)
    return {"ok": True, "data": None}


@router.get("/study-groups/{groupId}/members")
def list_study_group_members(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    _require_visible_group(request, auth_store, groupId)
    members = auth_store.list_study_group_members(groupId)
    return {"ok": True, "data": [_member_to_dto(member) for member in members]}


@router.post("/study-groups/{groupId}/members/invite")
def invite_study_group_member(
    groupId: str,
    req: InviteStudyGroupMemberRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group management denied")
    target = auth_store.get_user_by_public_uid(req.publicUid)
    if target.status != "active":
        raise HTTPException(status_code=404, detail="User not found")
    member = auth_store.invite_study_group_member(
        groupId,
        target_user_id=target.user_id,
        role=req.role,
        actor_user_id=user.user_id,
    )
    return {"ok": True, "data": _member_to_dto(member)}


@router.patch("/study-groups/{groupId}/members/{userId}")
def update_study_group_member_role(
    groupId: str,
    userId: str,
    req: UpdateStudyGroupMemberRoleRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group_members(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group member management denied")
    member = auth_store.update_study_group_member_role(
        groupId,
        target_user_id=userId,
        role=req.role,
        actor_user_id=user.user_id,
    )
    return {"ok": True, "data": _member_to_dto(member)}


@router.delete("/study-groups/{groupId}/members/{userId}")
def remove_study_group_member(groupId: str, userId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group_members(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group member management denied")
    auth_store.remove_study_group_member(groupId, target_user_id=userId, actor_user_id=user.user_id)
    return {"ok": True, "data": None}


@router.post("/study-groups/{groupId}/join-requests")
def create_study_group_join_request(
    groupId: str,
    req: CreateStudyGroupJoinRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    _require_visible_group(request, auth_store, groupId)
    item = auth_store.create_study_group_join_request(groupId, requester_user_id=user.user_id, message=req.message)
    return {"ok": True, "data": _join_request_to_dto(item)}


@router.get("/study-groups/{groupId}/join-requests")
def list_study_group_join_requests(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group management denied")
    requests = auth_store.list_study_group_join_requests(groupId)
    return {"ok": True, "data": [_join_request_to_dto(item) for item in requests]}


@router.patch("/study-groups/{groupId}/join-requests/{requestId}")
def review_study_group_join_request(
    groupId: str,
    requestId: str,
    req: ReviewStudyGroupJoinRequestRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group, is_admin = _require_visible_group(request, auth_store, groupId)
    if not _can_manage_group(group, is_admin=is_admin):
        raise HTTPException(status_code=403, detail="Study group management denied")
    item = auth_store.review_study_group_join_request(
        groupId,
        request_id=requestId,
        actor_user_id=user.user_id,
        status=req.status,
    )
    return {"ok": True, "data": _join_request_to_dto(item)}


@router.get("/study-groups/{groupId}/posts")
def list_study_group_posts(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    _require_visible_group(request, auth_store, groupId)
    posts = auth_store.list_study_group_posts(groupId)
    return {"ok": True, "data": [_post_to_dto(post) for post in posts]}


@router.get("/study-groups/{groupId}/comments")
def list_study_group_post_comments(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    _require_visible_group(request, auth_store, groupId)
    comments = auth_store.list_study_group_post_comments(groupId)
    return {"ok": True, "data": [_post_comment_to_dto(comment) for comment in comments]}


@router.post("/study-groups/{groupId}/posts")
def create_study_group_post(
    groupId: str,
    req: CreateStudyGroupPostRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group, _ = _require_visible_group(request, auth_store, groupId)
    if group.member_role is None:
        raise HTTPException(status_code=403, detail="Only study group members can post")
    post = auth_store.create_study_group_post(groupId, author_user_id=user.user_id, kind=req.kind, content=req.content)
    return {"ok": True, "data": _post_to_dto(post)}


@router.delete("/study-groups/{groupId}/posts/{postId}")
def delete_study_group_post(
    groupId: str,
    postId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    _require_visible_group(request, auth_store, groupId)
    post = auth_store.delete_study_group_post(groupId, postId, actor_user_id=user.user_id)
    return {"ok": True, "data": _post_to_dto(post)}


@router.post("/study-groups/{groupId}/posts/{postId}/comments")
def create_study_group_post_comment(
    groupId: str,
    postId: str,
    req: CreateStudyGroupPostCommentRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    group, _ = _require_visible_group(request, auth_store, groupId)
    if group.member_role is None:
        raise HTTPException(status_code=403, detail="Only study group members can comment")
    comment = auth_store.create_study_group_post_comment(groupId, postId, author_user_id=user.user_id, content=req.content)
    return {"ok": True, "data": _post_comment_to_dto(comment)}


@router.delete("/study-groups/{groupId}/comments/{commentId}")
def delete_study_group_post_comment(
    groupId: str,
    commentId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    _require_visible_group(request, auth_store, groupId)
    comment = auth_store.delete_study_group_post_comment(groupId, commentId, actor_user_id=user.user_id)
    return {"ok": True, "data": _post_comment_to_dto(comment)}
