from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple, TypeAlias

from backend.models.enums import ClientRuntimeKind, ReviewChainTemplateItemKind, RuntimeCapability
from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, Timestamp


# Spec 1.0.5 / 0b.1.5a: defaults are fixed for cross-implementation consistency.
DEFAULT_AGGREGATION_K_NODE: int = 10
DEFAULT_AGGREGATION_K_POINT: int = 200
DEFAULT_PUSH_MIN_RECALL_POINTS_TO_ENABLE: int = 30
DEFAULT_PUSH_MAX_HISTORY_LEN: int = 20


@dataclass(frozen=True, slots=True)
class ReviewChainTemplateItem:
    kind: ReviewChainTemplateItemKind
    count: Optional[int] = None

    def effective_count(self) -> int:
        if self.kind != ReviewChainTemplateItemKind.REVIEW_TASK:
            return 0
        return 1 if self.count is None else int(self.count)

    def validate_write_time(self) -> None:
        if self.kind == ReviewChainTemplateItemKind.CONVERGENCE:
            if self.count is not None:
                raise PreconditionFailure("ReviewChainTemplateItem(CONVERGENCE).count must be omitted")
            return
        if self.kind == ReviewChainTemplateItemKind.REVIEW_TASK:
            n = self.effective_count()
            if n < 1:
                raise PreconditionFailure("ReviewChainTemplateItem(REVIEW_TASK).count must be >= 1")
            return
        raise PreconditionFailure(f"Unknown ReviewChainTemplateItemKind: {self.kind}")


ReviewChainTemplate: TypeAlias = Tuple[ReviewChainTemplateItem, ...]


def validate_review_chain_template_write_time(template: ReviewChainTemplate) -> None:
    if template is None or len(template) == 0:
        raise PreconditionFailure("ReviewChainTemplate must be non-empty")

    has_convergence = False
    for item in template:
        if item is None:
            raise PreconditionFailure("ReviewChainTemplate contains null item")
        item.validate_write_time()
        if item.kind == ReviewChainTemplateItemKind.CONVERGENCE:
            has_convergence = True

    if not has_convergence:
        raise PreconditionFailure("ReviewChainTemplate must contain at least one CONVERGENCE")


@dataclass(frozen=True, slots=True)
class LayerConfig:
    review_chain_template: ReviewChainTemplate
    aggregation_k_node: int
    aggregation_k_point: int

    def validate_write_time(self) -> None:
        validate_review_chain_template_write_time(self.review_chain_template)
        if int(self.aggregation_k_node) < 1:
            raise PreconditionFailure("LayerConfig.aggregation_k_node must be >= 1")
        if int(self.aggregation_k_point) < 1:
            raise PreconditionFailure("LayerConfig.aggregation_k_point must be >= 1")


def default_layer_config() -> LayerConfig:
    return LayerConfig(
        review_chain_template=(ReviewChainTemplateItem(kind=ReviewChainTemplateItemKind.CONVERGENCE),),
        aggregation_k_node=DEFAULT_AGGREGATION_K_NODE,
        aggregation_k_point=DEFAULT_AGGREGATION_K_POINT,
    )


@dataclass(frozen=True, slots=True)
class LocalServiceConfig:
    base_url: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None

    def validate_write_time(self) -> None:
        if self.base_url is None or not str(self.base_url).strip():
            raise PreconditionFailure("LocalServiceConfig.base_url must be non-empty")
        if str(self.base_url) != str(self.base_url).rstrip():
            raise PreconditionFailure("LocalServiceConfig.base_url must not contain trailing whitespace")
        if self.api_key is not None and str(self.api_key) != str(self.api_key).rstrip():
            raise PreconditionFailure("LocalServiceConfig.api_key must not contain trailing whitespace")
        if self.model_name is not None and str(self.model_name) != str(self.model_name).rstrip():
            raise PreconditionFailure("LocalServiceConfig.model_name must not contain trailing whitespace")

    @property
    def model(self) -> Optional[str]:
        return self.model_name


@dataclass(frozen=True, slots=True)
class LocalModelConfig:
    asr: Optional[LocalServiceConfig] = None
    llm_qa: Optional[LocalServiceConfig] = None
    recommender: Optional[LocalServiceConfig] = None
    story_generator: Optional[LocalServiceConfig] = None

    def validate_write_time(self) -> None:
        if self.asr is not None:
            self.asr.validate_write_time()
        if self.llm_qa is not None:
            self.llm_qa.validate_write_time()
        if self.recommender is not None:
            self.recommender.validate_write_time()
        if self.story_generator is not None:
            self.story_generator.validate_write_time()


@dataclass(frozen=True, slots=True)
class NativeRuntimeConfig:
    runtime_kind: ClientRuntimeKind
    capabilities: FrozenSet[RuntimeCapability]
    local_models: LocalModelConfig

    def validate_runtime(self) -> None:
        if not isinstance(self.runtime_kind, ClientRuntimeKind):
            raise PreconditionFailure("NativeRuntimeConfig.runtime_kind must be ClientRuntimeKind")
        if self.capabilities is None:
            raise PreconditionFailure("NativeRuntimeConfig.capabilities must not be null")
        for capability in self.capabilities:
            if not isinstance(capability, RuntimeCapability):
                raise PreconditionFailure("NativeRuntimeConfig.capabilities contains invalid capability")
        if self.local_models is None:
            raise PreconditionFailure("NativeRuntimeConfig.local_models must not be null")
        self.local_models.validate_write_time()


@dataclass(frozen=True, slots=True)
class RecallPointPushConfig:
    min_recall_points_to_enable: int
    max_history_len: int

    def validate_write_time(self) -> None:
        if int(self.min_recall_points_to_enable) < 0:
            raise PreconditionFailure("RecallPointPushConfig.min_recall_points_to_enable must be >= 0")
        if int(self.max_history_len) < 0:
            raise PreconditionFailure("RecallPointPushConfig.max_history_len must be >= 0")


def default_local_model_config() -> LocalModelConfig:
    return LocalModelConfig(asr=None, llm_qa=None, recommender=None, story_generator=None)


def default_push_config() -> RecallPointPushConfig:
    return RecallPointPushConfig(
        min_recall_points_to_enable=DEFAULT_PUSH_MIN_RECALL_POINTS_TO_ENABLE,
        max_history_len=DEFAULT_PUSH_MAX_HISTORY_LEN,
    )


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    project_id: ProjectId
    layer_configs: Dict[int, LayerConfig]
    push_config: RecallPointPushConfig
    updated_at: Timestamp

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("ProjectConfig.project_id must be non-empty")
        if self.layer_configs is None:
            raise PreconditionFailure("ProjectConfig.layer_configs must not be null")
        if self.push_config is None:
            raise PreconditionFailure("ProjectConfig.push_config must not be null")
        if 0 not in self.layer_configs:
            raise PreconditionFailure("ProjectConfig.layer_configs must include layer_index=0")

        for layer_index, cfg in self.layer_configs.items():
            if int(layer_index) < 0:
                raise PreconditionFailure("ProjectConfig.layer_configs keys must be >= 0")
            if cfg is None:
                raise PreconditionFailure("ProjectConfig.layer_configs contains null LayerConfig")
            cfg.validate_write_time()

        self.push_config.validate_write_time()


def default_project_config(*, project_id: ProjectId, updated_at: Timestamp) -> ProjectConfig:
    return ProjectConfig(
        project_id=project_id,
        layer_configs={0: default_layer_config()},
        push_config=default_push_config(),
        updated_at=updated_at,
    )
