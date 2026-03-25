from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import conlist


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    projectRoot: Optional[str] = None
    initialSourceKind: Optional[str] = None


class EditProjectRequest(BaseModel):
    title: str = Field(min_length=1)


class SetProjectMaterialSourceBindingRequest(BaseModel):
    sourceKind: str = Field(min_length=1)
    sourceRootLabel: Optional[str] = None

class AuthCredentialsRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


class UpdateProfileRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=40)
    bio: Optional[str] = Field(default="", max_length=500)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(min_length=8)
    newPassword: str = Field(min_length=8)


class CreateStudyGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=1000)
    visibility: str = Field(min_length=1)
    joinPolicy: str = Field(min_length=1)


class UpdateStudyGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=1000)
    visibility: str = Field(min_length=1)
    joinPolicy: str = Field(min_length=1)


class CreateStudyGroupPostRequest(BaseModel):
    kind: str = Field(min_length=1)
    content: str = Field(min_length=1, max_length=2000)


class CreateStudyGroupPostCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(min_length=1)


class UpdateStudyGroupStatusRequest(BaseModel):
    status: str = Field(min_length=1)


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(min_length=1)
    enabled: bool = True


class UpdateStudyGroupMemberRoleRequest(BaseModel):
    role: str = Field(min_length=1)


class CreateStudyGroupJoinRequest(BaseModel):
    message: Optional[str] = Field(default="", max_length=300)


class ReviewStudyGroupJoinRequestRequest(BaseModel):
    status: str = Field(min_length=1)


class InviteStudyGroupMemberRequest(BaseModel):
    publicUid: str = Field(min_length=1)
    role: str = Field(default="member", min_length=1)


class AddInstanceRequest(BaseModel):
    materialId: str = Field(min_length=1)


class ImportBrowserDirectoryRequest(BaseModel):
    rootTitle: Optional[str] = None
    relativeFilePaths: List[str] = Field(default_factory=list)


class AddLearningObjectLeafRequest(BaseModel):
    parentId: Optional[str] = None
    instanceId: str = Field(min_length=1)
    title: str = Field(min_length=1)


class AddLearningObjectContainerRequest(BaseModel):
    parentId: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    title: str = Field(min_length=1)


class AnchorDTO(BaseModel):
    instanceId: str = Field(min_length=1)
    position: str = Field(min_length=1)

class ContentBlockDTO(BaseModel):
    kind: str = Field(min_length=1)
    text: Optional[str] = None
    assetId: Optional[str] = None


class LearningItemDTO(BaseModel):
    question: conlist(ContentBlockDTO, min_items=1)
    answer: conlist(ContentBlockDTO, min_items=1)
    anchor: AnchorDTO


class SubmitLearningTaskRequest(BaseModel):
    title: str = Field(min_length=1)
    items: conlist(LearningItemDTO, min_items=1)


class EditLearningTaskRequest(BaseModel):
    title: str = Field(min_length=1)


class EditRecallPointRequest(BaseModel):
    question: conlist(ContentBlockDTO, min_items=1)
    answer: conlist(ContentBlockDTO, min_items=1)
    anchor: AnchorDTO

class AppendedInsightDTO(BaseModel):
    recallPointId: str = Field(min_length=1)
    insight: conlist(ContentBlockDTO, min_items=1)


class CommitReviewTaskRequest(BaseModel):
    canRecall: conlist(int, min_items=1)
    appendedInsights: Optional[List[AppendedInsightDTO]] = None


class BulkRemapRecallPointsInstanceRequest(BaseModel):
    fromInstanceId: str = Field(min_length=1)
    toInstanceId: str = Field(min_length=1)
    recallPointIds: Optional[List[str]] = None


class ManualRollUpRequest(BaseModel):
    title: Optional[str] = None


class ReviewChainTemplateItemDTO(BaseModel):
    kind: str = Field(min_length=1)
    count: Optional[int] = None


class SetLayerConfigRequest(BaseModel):
    reviewChainTemplate: Optional[List[ReviewChainTemplateItemDTO]] = None
    kNode: Optional[int] = None
    kPoint: Optional[int] = None


class RequestAsrRequest(BaseModel):
    recallPointId: str = Field(min_length=1)
    centerMs: int = Field(ge=0)
    preMs: int = Field(ge=0)
    postMs: int = Field(ge=0)
    provider: Optional[str] = None
