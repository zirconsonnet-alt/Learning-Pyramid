from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from adapter.auth import require_admin_user, require_super_admin_user
from adapter.deps import get_auth_store
from adapter.schemas import UpdateStudyGroupStatusRequest, UpdateUserRoleRequest, UpdateUserStatusRequest
from backend.system.auth_store import (
    AdminActionLog,
    AdminStudyGroupComment,
    AdminStudyGroupPost,
    AdminUser,
    AdminUserStudyGroup,
    AuthStore,
    StudyGroup,
    StudyGroupJoinRequest,
    StudyGroupMember,
    StudyGroupPost,
    StudyGroupPostComment,
)

router = APIRouter()


def _admin_user_to_dto(user: AdminUser) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "createdAt": user.created_at,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": None if not user.avatar_key else f"/api/profile/avatar/{user.user_id}?v={user.updated_at}",
        "status": user.status,
        "updatedAt": user.updated_at,
        "roles": list(user.roles),
    }


def _auth_user_to_admin_dto(user_id: str, auth_store: AuthStore) -> dict[str, object]:
    user = auth_store.get_user_by_id(user_id)
    return {
        "userId": user.user_id,
        "email": user.email,
        "createdAt": user.created_at,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": None if not user.avatar_key else f"/api/profile/avatar/{user.user_id}?v={user.updated_at}",
        "status": user.status,
        "updatedAt": user.updated_at,
        "roles": list(auth_store.list_user_roles(user.user_id)),
    }


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
        "avatarUrl": None if not group.avatar_key else f"/api/study-groups/{group.group_id}/avatar?v={group.updated_at}",
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
        "memberCount": group.member_count,
        "memberRole": group.member_role,
        "joinRequestStatus": group.join_request_status,
    }


def _admin_user_group_to_dto(group: AdminUserStudyGroup) -> dict[str, object]:
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
        "avatarUrl": None if not group.avatar_key else f"/api/study-groups/{group.group_id}/avatar?v={group.updated_at}",
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
        "memberCount": group.member_count,
        "memberRole": group.member_role,
        "joinedAt": group.joined_at,
    }


def _group_member_to_dto(member: StudyGroupMember) -> dict[str, object]:
    return {
        "userId": member.user_id,
        "publicUid": member.public_uid,
        "nickname": member.nickname,
        "avatarUrl": None if not member.avatar_key else f"/api/profile/avatar/{member.user_id}",
        "role": member.role,
        "joinedAt": member.joined_at,
    }


def _group_post_to_dto(post: StudyGroupPost) -> dict[str, object]:
    return {
        "postId": post.post_id,
        "groupId": post.group_id,
        "authorUserId": post.author_user_id,
        "authorPublicUid": post.author_public_uid,
        "authorNickname": post.author_nickname,
        "authorAvatarUrl": None if not post.author_avatar_key else f"/api/profile/avatar/{post.author_user_id}",
        "kind": post.kind,
        "content": post.content,
        "createdAt": post.created_at,
        "updatedAt": post.updated_at,
    }


def _group_comment_to_dto(comment: StudyGroupPostComment) -> dict[str, object]:
    return {
        "commentId": comment.comment_id,
        "groupId": comment.group_id,
        "postId": comment.post_id,
        "authorUserId": comment.author_user_id,
        "authorPublicUid": comment.author_public_uid,
        "authorNickname": comment.author_nickname,
        "authorAvatarUrl": None if not comment.author_avatar_key else f"/api/profile/avatar/{comment.author_user_id}",
        "content": comment.content,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
    }


def _group_join_request_to_dto(item: StudyGroupJoinRequest) -> dict[str, object]:
    return {
        "requestId": item.request_id,
        "groupId": item.group_id,
        "requesterUserId": item.requester_user_id,
        "requesterPublicUid": item.requester_public_uid,
        "requesterNickname": item.requester_nickname,
        "requesterAvatarUrl": None if not item.requester_avatar_key else f"/api/profile/avatar/{item.requester_user_id}",
        "message": item.message,
        "status": item.status,
        "createdAt": item.created_at,
        "reviewedAt": item.reviewed_at,
        "reviewedByUserId": item.reviewed_by_user_id,
    }


def _admin_post_to_dto(post: AdminStudyGroupPost) -> dict[str, object]:
    return {
        "postId": post.post_id,
        "groupId": post.group_id,
        "groupName": post.group_name,
        "authorUserId": post.author_user_id,
        "authorPublicUid": post.author_public_uid,
        "authorNickname": post.author_nickname,
        "authorAvatarUrl": None if not post.author_avatar_key else f"/api/profile/avatar/{post.author_user_id}",
        "kind": post.kind,
        "content": post.content,
        "createdAt": post.created_at,
        "updatedAt": post.updated_at,
        "commentCount": post.comment_count,
    }


def _admin_comment_to_dto(comment: AdminStudyGroupComment) -> dict[str, object]:
    return {
        "commentId": comment.comment_id,
        "groupId": comment.group_id,
        "groupName": comment.group_name,
        "postId": comment.post_id,
        "postKind": comment.post_kind,
        "postExcerpt": comment.post_excerpt,
        "authorUserId": comment.author_user_id,
        "authorPublicUid": comment.author_public_uid,
        "authorNickname": comment.author_nickname,
        "authorAvatarUrl": None if not comment.author_avatar_key else f"/api/profile/avatar/{comment.author_user_id}",
        "content": comment.content,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
    }


def _admin_action_log_to_dto(item: AdminActionLog) -> dict[str, object]:
    return {
        "logId": item.log_id,
        "actorUserId": item.actor_user_id,
        "actorPublicUid": item.actor_public_uid,
        "actorNickname": item.actor_nickname,
        "actorAvatarUrl": None if not item.actor_avatar_key else f"/api/profile/avatar/{item.actor_user_id}",
        "actionType": item.action_type,
        "targetKind": item.target_kind,
        "targetId": item.target_id,
        "summary": item.summary,
        "createdAt": item.created_at,
    }


@router.get("/admin/overview")
def get_admin_overview(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    return {"ok": True, "data": auth_store.get_admin_overview()}


@router.get("/admin/users")
def list_users(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    users = auth_store.list_users(search=search, status=status, role=role, limit=limit)
    return {"ok": True, "data": [_admin_user_to_dto(user) for user in users]}


@router.get("/admin/users/{userId}")
def get_user_detail(userId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    user = auth_store.get_user_by_id(userId)
    groups = auth_store.list_admin_user_study_groups(userId, limit=200)
    return {
        "ok": True,
        "data": {
            **_auth_user_to_admin_dto(user.user_id, auth_store),
            "groups": [_admin_user_group_to_dto(group) for group in groups],
        },
    }


@router.patch("/admin/users/{userId}/status")
def update_user_status(
    userId: str,
    req: UpdateUserStatusRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    updated = auth_store.set_user_status(userId, status=req.status)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="user.status_updated",
        target_kind="user",
        target_id=updated.user_id,
        summary=f"Set user {updated.public_uid} status to {updated.status}",
    )
    return {"ok": True, "data": _auth_user_to_admin_dto(updated.user_id, auth_store)}


@router.patch("/admin/users/{userId}/roles")
def update_user_role(
    userId: str,
    req: UpdateUserRoleRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_super_admin_user(request, auth_store)
    auth_store.set_user_global_role(userId, role=req.role, enabled=req.enabled, granted_by_user_id=actor.user_id)
    target_user = auth_store.get_user_by_id(userId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="user.role_updated",
        target_kind="user",
        target_id=target_user.user_id,
        summary=f"{'Granted' if req.enabled else 'Revoked'} {req.role} for user {target_user.public_uid}",
    )
    return {"ok": True, "data": _auth_user_to_admin_dto(userId, auth_store)}


@router.get("/admin/groups")
def list_groups(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    groups = auth_store.list_all_study_groups(search=search, status=status, limit=limit)
    return {"ok": True, "data": [_group_to_dto(group) for group in groups]}


@router.get("/admin/groups/{groupId}")
def get_group_detail(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    group = auth_store.get_study_group(groupId, viewer_user_id=actor.user_id)
    members = auth_store.list_study_group_members(groupId)
    join_requests = auth_store.list_study_group_join_requests(groupId, status=None, limit=200)
    posts = auth_store.list_study_group_posts(groupId, limit=200)
    comments = auth_store.list_study_group_post_comments(groupId, limit=400)
    return {
        "ok": True,
        "data": {
            **_group_to_dto(group),
            "members": [_group_member_to_dto(member) for member in members],
            "joinRequests": [_group_join_request_to_dto(item) for item in join_requests],
            "posts": [_group_post_to_dto(post) for post in posts],
            "comments": [_group_comment_to_dto(comment) for comment in comments],
        },
    }


@router.patch("/admin/groups/{groupId}/status")
def update_group_status(
    groupId: str,
    req: UpdateStudyGroupStatusRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    group = auth_store.set_study_group_status(groupId, status=req.status)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="group.status_updated",
        target_kind="study_group",
        target_id=group.group_id,
        summary=f"Set study group {group.name} status to {group.status}",
    )
    return {"ok": True, "data": _group_to_dto(group)}


@router.get("/admin/activity")
@router.get("/admin/audit-logs")
def list_admin_activity(request: Request, limit: int = 50, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    logs = auth_store.list_admin_action_logs(limit=limit)
    return {"ok": True, "data": [_admin_action_log_to_dto(item) for item in logs]}


@router.get("/admin/content/posts")
def list_admin_posts(
    request: Request,
    search: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    posts = auth_store.list_admin_study_group_posts(search=search, limit=limit)
    return {"ok": True, "data": [_admin_post_to_dto(post) for post in posts]}


@router.get("/admin/content/comments")
def list_admin_comments(
    request: Request,
    search: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    comments = auth_store.list_admin_study_group_comments(search=search, limit=limit)
    return {"ok": True, "data": [_admin_comment_to_dto(comment) for comment in comments]}


@router.delete("/admin/content/posts/{postId}")
def delete_admin_post(postId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    deleted = auth_store.delete_admin_study_group_post(postId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="content.post_deleted",
        target_kind="study_group_post",
        target_id=deleted.post_id,
        summary=f"Deleted post in {deleted.group_name} by {deleted.author_public_uid}",
    )
    return {"ok": True, "data": _admin_post_to_dto(deleted)}


@router.delete("/admin/content/comments/{commentId}")
def delete_admin_comment(commentId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    deleted = auth_store.delete_admin_study_group_comment(commentId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="content.comment_deleted",
        target_kind="study_group_comment",
        target_id=deleted.comment_id,
        summary=f"Deleted comment in {deleted.group_name} by {deleted.author_public_uid}",
    )
    return {"ok": True, "data": _admin_comment_to_dto(deleted)}
