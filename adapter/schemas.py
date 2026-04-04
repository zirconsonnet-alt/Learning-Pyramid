from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field
from pydantic import conlist


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    projectRoot: Optional[str] = None
    initialSourceKind: Optional[str] = None
    initialProjectType: Optional[str] = None


class EditProjectRequest(BaseModel):
    title: str = Field(min_length=1)


class SetProjectMaterialSourceBindingRequest(BaseModel):
    sourceKind: str = Field(min_length=1)
    sourceRootLabel: Optional[str] = None

class AuthCredentialsRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RegisterAuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    inviteCode: Optional[str] = Field(default=None, min_length=1, max_length=32)


class PreviewMembershipOrderRequest(BaseModel):
    couponId: Optional[str] = Field(default=None, min_length=1)


class CreateMembershipOrderRequest(BaseModel):
    provider: str = Field(min_length=1)
    couponId: Optional[str] = Field(default=None, min_length=1)


class ConfirmMembershipPaymentRequest(BaseModel):
    orderId: str = Field(min_length=1)
    providerTradeNo: Optional[str] = Field(default=None, min_length=1)


class BindInviteCodeRequest(BaseModel):
    inviteCode: str = Field(min_length=1, max_length=32)


class AdminGrantMembershipCouponRequest(BaseModel):
    userId: str = Field(min_length=1)
    amountCent: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=60)
    expiresInDays: int = Field(ge=1, le=365)
    minSpendCent: int = Field(default=0, ge=0)


class AdminVoidMembershipCouponRequest(BaseModel):
    reason: Optional[str] = Field(default="", max_length=200)


class AdminRefundMembershipOrderRequest(BaseModel):
    reason: Optional[str] = Field(default="", max_length=200)


class UpdateProfileRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=40)
    bio: Optional[str] = Field(default="", max_length=500)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(min_length=8)
    newPassword: str = Field(min_length=8)


class CreateFriendRequestRequest(BaseModel):
    publicUid: str = Field(min_length=1)
    message: Optional[str] = Field(default="", max_length=200)


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(min_length=1)


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(min_length=1)
    enabled: bool = True


class AddInstanceRequest(BaseModel):
    materialId: str = Field(min_length=1)


class ImportBrowserDirectoryRequest(BaseModel):
    rootTitle: Optional[str] = None
    relativeFilePaths: List[str] = Field(default_factory=list)


class BaiduNetdiskImportItemDTO(BaseModel):
    fileId: str = Field(min_length=1)
    path: str = Field(min_length=1)
    name: Optional[str] = None
    isDir: bool = False
    sizeBytes: Optional[int] = Field(default=None, ge=0)
    mimeType: Optional[str] = None
    durationMs: Optional[int] = Field(default=None, ge=0)


class ImportLearningObjectsFromBaiduNetdiskRequest(BaseModel):
    accountId: str = Field(min_length=1)
    items: conlist(BaiduNetdiskImportItemDTO, min_items=1)


class AddLearningObjectLeafRequest(BaseModel):
    parentId: Optional[str] = None
    instanceId: str = Field(min_length=1)
    title: str = Field(min_length=1)


class AddLearningObjectContainerRequest(BaseModel):
    parentId: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    title: str = Field(min_length=1)


class BookOutlineItemDTO(BaseModel):
    depth: int = Field(ge=0)
    title: str = Field(min_length=1)


class InitializeBookLearningObjectsRequest(BaseModel):
    items: conlist(BookOutlineItemDTO, min_items=1)


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
    anchor: Optional[AnchorDTO] = None


class SubmitLearningTaskRequest(BaseModel):
    title: str = Field(min_length=1)
    items: conlist(LearningItemDTO, min_items=1)


class EditLearningTaskRequest(BaseModel):
    title: str = Field(min_length=1)


class EditLearningTaskNodeRequest(BaseModel):
    title: str = Field(min_length=1)


class EditRecallPointRequest(BaseModel):
    question: conlist(ContentBlockDTO, min_items=1)
    answer: conlist(ContentBlockDTO, min_items=1)
    anchor: Optional[AnchorDTO] = None

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
    thresholdRollUpEnabled: Optional[bool] = None


class SetReviewRecommendationConfigRequest(BaseModel):
    minRecallPointsToEnable: Optional[int] = Field(default=None, ge=0)
    maxHistoryLen: Optional[int] = Field(default=None, ge=0)
    recommendedBatchSize: Optional[int] = Field(default=None, ge=1)
    forgettingCurveDecayPerDay: Optional[float] = Field(default=None, gt=0)


class TransientServiceConfigRequest(BaseModel):
    baseUrl: str = Field(min_length=1)
    modelName: Optional[str] = None
    apiKey: Optional[str] = None


class RequestAsrRequest(BaseModel):
    recallPointId: str = Field(min_length=1)
    centerMs: int = Field(ge=0)
    preMs: int = Field(ge=0)
    postMs: int = Field(ge=0)
    provider: Optional[str] = None
    serviceConfig: Optional[TransientServiceConfigRequest] = None


class RequestInstanceAsrRequest(BaseModel):
    startMs: int = Field(ge=0)
    endMs: int = Field(gt=0)
    provider: Optional[str] = None
    serviceConfig: Optional[TransientServiceConfigRequest] = None


class UpdateGlobalLlmSettingsRequest(BaseModel):
    baseUrl: Optional[str] = None
    modelName: Optional[str] = None
    apiKey: Optional[str] = None
    promptAssemblyMode: Optional[str] = None
    clearApiKey: bool = False


class UpdateUserServiceSettingsRequest(BaseModel):
    baseUrl: Optional[str] = None
    modelName: Optional[str] = None
    apiKey: Optional[str] = None
    promptAssemblyMode: Optional[str] = None
    clearApiKey: bool = False


class AskLlmRequest(BaseModel):
    prompt: str = Field(min_length=1)
    systemPrompt: Optional[str] = None
    modelName: Optional[str] = None
    temperature: Optional[float] = None


class AskProjectLlmRequest(BaseModel):
    prompt: str = Field(min_length=1)
    systemPrompt: Optional[str] = None
    supplementalContext: Optional[str] = None
    modelName: Optional[str] = None
    temperature: Optional[float] = None
    recallPointId: Optional[str] = None
    learningTaskNodeId: Optional[str] = None
    learningObjectNodeId: Optional[str] = None


class AskProjectLlmRawChatCompletionRequest(BaseModel):
    messages: conlist(dict[str, Any], min_items=1)
    tools: Optional[list[dict[str, Any]]] = None
    toolChoice: Optional[Any] = None
    parallelToolCalls: Optional[bool] = None
    responseFormat: Optional[dict[str, Any]] = None
    modelName: Optional[str] = None
    temperature: Optional[float] = None
