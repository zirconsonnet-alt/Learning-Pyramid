from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import conlist


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    projectRoot: Optional[str] = None


class SetProjectMaterialSourceBindingRequest(BaseModel):
    sourceKind: str = Field(min_length=1)
    desktopAgentId: Optional[str] = None
    sourceRootLabel: Optional[str] = None


class PairDesktopAgentRequest(BaseModel):
    pairingCode: str = Field(min_length=1)
    deviceName: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    appVersion: str = Field(min_length=1)


class RefreshDesktopAgentTokenRequest(BaseModel):
    refreshToken: str = Field(min_length=1)


class AuthCredentialsRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


class ProvisionDesktopAgentRequest(BaseModel):
    deviceName: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    appVersion: str = Field(min_length=1)


class CompleteDesktopAgentAccountSetupRequest(BaseModel):
    agentId: str = Field(min_length=1)
    projectId: str = Field(min_length=1)
    sourceRootLabel: Optional[str] = None


class AddInstanceRequest(BaseModel):
    materialId: str = Field(min_length=1)


class ClientMediaManifestEntryRequest(BaseModel):
    relativePath: str = Field(min_length=1)
    displayName: Optional[str] = None
    mediaKind: Optional[str] = None
    sizeBytes: Optional[int] = Field(default=None, ge=0)
    modifiedAt: Optional[str] = None


class SyncClientMediaManifestRequest(BaseModel):
    rootTitle: Optional[str] = None
    entries: List[ClientMediaManifestEntryRequest] = Field(default_factory=list)


class DesktopAgentManifestSyncRequest(BaseModel):
    projectId: str = Field(min_length=1)
    agentId: str = Field(min_length=1)
    rootTitle: Optional[str] = None
    entries: List[ClientMediaManifestEntryRequest] = Field(default_factory=list)


class DesktopAgentDiagnosticEventRequest(BaseModel):
    level: str = Field(min_length=1)
    category: str = Field(min_length=1)
    eventType: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict = Field(default_factory=dict)
    projectId: Optional[str] = None
    instanceId: Optional[str] = None
    relativePath: Optional[str] = None
    createdAt: Optional[str] = None


class DesktopAgentHlsJobStateRequest(BaseModel):
    state: str = Field(min_length=1)
    message: Optional[str] = None


class CreateDesktopAgentSetupSessionRequest(BaseModel):
    preferredProjectId: Optional[str] = None


class CompleteDesktopAgentSetupRequest(BaseModel):
    setupCode: str = Field(min_length=1)
    agentId: str = Field(min_length=1)
    projectId: str = Field(min_length=1)
    sourceRootLabel: Optional[str] = None


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


class LocalServiceConfigDTO(BaseModel):
    baseUrl: str = Field(min_length=1)
    apiKey: Optional[str] = None
    model: Optional[str] = None


class SetExternalServicesRequest(BaseModel):
    asr: Optional[LocalServiceConfigDTO] = None

class RequestAsrRequest(BaseModel):
    recallPointId: str = Field(min_length=1)
    centerMs: int = Field(ge=0)
    preMs: int = Field(ge=0)
    postMs: int = Field(ge=0)
    provider: Optional[str] = None
