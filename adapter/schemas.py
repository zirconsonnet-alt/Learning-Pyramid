from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, root_validator
from pydantic import conlist


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    projectRoot: Optional[str] = None
    initialSourceKind: Optional[str] = None
    initialProjectType: Optional[str] = None


class CreateSubjectRequest(BaseModel):
    title: str = Field(min_length=1)


class CreateStudyMaterialRequest(BaseModel):
    materialType: str = Field(min_length=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)


class EditSubjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class EditStudyMaterialRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


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
    humanCheckToken: Optional[str] = Field(default=None, min_length=1, max_length=2048)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    newPassword: str = Field(min_length=8)


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)


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


class CreateCommissionWithdrawalRequest(BaseModel):
    amountCent: int = Field(ge=1)


class StartWeChatPayoutBindingRequest(BaseModel):
    channel: str = Field(default="desktop_qr_official_account_h5", min_length=1, max_length=64)
    returnUrl: str = Field(min_length=1, max_length=2048)
    amountCent: int = Field(default=0, ge=0)


class CompleteWeChatPayoutBindingRequest(BaseModel):
    bindingAttemptId: str = Field(min_length=1)
    authorizationCode: str = Field(min_length=1, max_length=512)
    state: str = Field(min_length=1, max_length=512)
    confirmedLearningPyramidUserId: Optional[str] = Field(default=None, max_length=128)


class SyncCommissionWithdrawalRequest(BaseModel):
    reason: Optional[str] = Field(default="", max_length=200)


class AdminResolveCommissionWithdrawalRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    providerTransferNo: Optional[str] = Field(default=None, max_length=128)
    failureReason: Optional[str] = Field(default="", max_length=200)


class AdminGrantMembershipCouponRequest(BaseModel):
    userId: str = Field(min_length=1)
    amountCent: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=60)
    expiresInDays: int = Field(ge=1, le=365)
    minSpendCent: int = Field(default=0, ge=0)


class AdminGrantMembershipMonthsRequest(BaseModel):
    userId: str = Field(min_length=1)
    months: int = Field(ge=1, le=24)


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


class StudyRangeRequest(BaseModel):
    startMs: int = Field(ge=0)
    endMs: int = Field(gt=0)


class VideoWatchProgressRangeRequest(BaseModel):
    startMs: int = Field(ge=0)
    endMs: int = Field(gt=0)
    durationMs: Optional[int] = Field(default=None, ge=0)


class VideoWatchProgressCompletedRequest(BaseModel):
    durationMs: int = Field(gt=0)


class DailyStudyMetricEntryRequest(BaseModel):
    projectId: str = Field(min_length=1, max_length=200)
    dateKey: str = Field(min_length=10, max_length=10)
    schemaVersion: int = Field(default=1, ge=1)
    webPresenceMs: int = Field(default=0, ge=0)
    videoMs: int = Field(default=0, ge=0)
    recallEntryMs: int = Field(default=0, ge=0)
    aiQaMs: int = Field(default=0, ge=0)
    distractionMs: int = Field(default=0, ge=0)
    presenceRanges: List[StudyRangeRequest] = Field(default_factory=list)
    videoRanges: List[StudyRangeRequest] = Field(default_factory=list)
    recallEntryRanges: List[StudyRangeRequest] = Field(default_factory=list)
    aiQaRanges: List[StudyRangeRequest] = Field(default_factory=list)
    isPartitionComplete: bool = False
    effectiveMs: int = Field(default=0, ge=0)
    watchMs: int = Field(default=0, ge=0)
    composeMs: int = Field(default=0, ge=0)
    reviewMs: int = Field(default=0, ge=0)
    qaMs: int = Field(default=0, ge=0)
    effectiveRanges: List[StudyRangeRequest] = Field(default_factory=list)
    watchRanges: List[StudyRangeRequest] = Field(default_factory=list)
    composeRanges: List[StudyRangeRequest] = Field(default_factory=list)
    reviewRanges: List[StudyRangeRequest] = Field(default_factory=list)
    qaRanges: List[StudyRangeRequest] = Field(default_factory=list)


class SyncStudyMetricsRequest(BaseModel):
    projectIds: List[str] = Field(default_factory=list)
    dateFrom: Optional[str] = Field(default=None, min_length=10, max_length=10)
    dateTo: Optional[str] = Field(default=None, min_length=10, max_length=10)
    entries: List[DailyStudyMetricEntryRequest] = Field(default_factory=list)


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


class InitializeBookLearningObjectsFromMaterialRequest(BaseModel):
    sourceMaterialId: str = Field(min_length=1)


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
    references: List[str] = Field(default_factory=list)


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


class SetProjectRollUpStrategyRequest(BaseModel):
    rollUpStrategy: str = Field(min_length=1)


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


class UserPomodoroSettingsRequest(BaseModel):
    id: Optional[str] = None
    enabled: bool = False
    startTime: str = Field(default="19:00", min_length=4, max_length=5)
    focusMinutes: int = Field(ge=1, le=180)
    breakMinutes: int = Field(ge=1, le=60)
    pomodoroCount: int = Field(ge=1, le=12)
    projectIds: List[Optional[str]] = Field(default_factory=list)
    breakPrompt: str = Field(default="", max_length=200)
    focusPrompts: List[str] = Field(default_factory=list)


class UserPomodoroWeeklyScheduleRequest(BaseModel):
    mon: dict[str, Any]
    tue: dict[str, Any]
    wed: dict[str, Any]
    thu: dict[str, Any]
    fri: dict[str, Any]
    sat: dict[str, Any]
    sun: dict[str, Any]


class UserPomodoroMicroBreakSettingsRequest(BaseModel):
    enabled: bool = False
    minIntervalSeconds: int = Field(default=180, ge=30, le=3600)
    maxIntervalSeconds: int = Field(default=300, ge=30, le=3600)
    durationSeconds: int = Field(default=10, ge=5, le=300)

    @root_validator
    def validate_interval_order(cls, values: dict[str, Any]) -> dict[str, Any]:
        min_interval = int(values.get("minIntervalSeconds", 180))
        max_interval = int(values.get("maxIntervalSeconds", 300))
        if max_interval < min_interval:
            raise ValueError("maxIntervalSeconds must be greater than or equal to minIntervalSeconds")
        return values


class UserPomodoroConfigRequest(BaseModel):
    enabled: bool = False
    transitionSoundEnabled: bool = False
    defaultFocusPrompt: str = Field(default="", max_length=200)
    defaultBreakPrompt: str = Field(default="", max_length=200)
    microBreaks: UserPomodoroMicroBreakSettingsRequest = Field(default_factory=UserPomodoroMicroBreakSettingsRequest)
    weeklySchedule: UserPomodoroWeeklyScheduleRequest


class PomodoroTtsPreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class UpdateUserGlobalSettingsRequest(BaseModel):
    theme: Optional[str] = Field(default=None, max_length=40)
    pomodoro: UserPomodoroConfigRequest
    defaultProjectReviewTemplate: conlist(ReviewChainTemplateItemDTO, min_items=1)


class LearningPlanDTO(BaseModel):
    planId: str = Field(min_length=1, max_length=240)
    projectId: str = Field(min_length=1, max_length=200)
    title: str = Field(default="学习计划", max_length=120)
    targetKind: str = Field(default="PROJECT")
    learningObjectNodeIds: List[str] = Field(default_factory=list, max_items=500)
    targetDays: int = Field(default=1, ge=1, le=3650)
    createdDateKey: str = Field(min_length=10, max_length=10)
    dueDateKey: str = Field(min_length=10, max_length=10)
    archivedAt: Optional[int] = Field(default=None, ge=0)
    updatedAt: int = Field(default=0, ge=0)


class LearningPlanProgressSnapshotDTO(BaseModel):
    planId: str = Field(min_length=1, max_length=240)
    dateKey: str = Field(min_length=10, max_length=10)
    progressRatio: float = Field(default=0, ge=0, le=1)
    updatedAt: int = Field(default=0, ge=0)


class LearningPlansPayloadDTO(BaseModel):
    plans: List[LearningPlanDTO] = Field(default_factory=list, max_items=500)
    progressSnapshots: List[LearningPlanProgressSnapshotDTO] = Field(default_factory=list, max_items=5000)


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
