from dataclasses import dataclass
from typing import Optional, Tuple

from backend.models.enums import RecallPointReviewResult
from backend.models.recall_point import RecallPoint
from backend.models.types import RecallPointId, ReviewTaskId, Timestamp


@dataclass(frozen=True, slots=True)
class RecallPointReviewRecommendation:
    recall_point: RecallPoint
    review_recommendation_index: float
    estimated_memory_strength: float
    weighted_success_ratio: float
    last_reviewed_at: Optional[Timestamp]
    last_review_result: Optional[RecallPointReviewResult]
    review_count: int


@dataclass(frozen=True, slots=True)
class RecallPointReviewRecommendationPage:
    items: Tuple[RecallPointReviewRecommendation, ...]
    total_count: int
    offset: int
    limit: int
    next_offset: Optional[int]


@dataclass(frozen=True, slots=True)
class RecallPointReviewHistoryItem:
    review_task_id: ReviewTaskId
    occurred_at: Timestamp
    result: RecallPointReviewResult


@dataclass(frozen=True, slots=True)
class RecallPointReviewProjection:
    recall_point_id: RecallPointId
    calculated_at: Timestamp
    review_recommendation_index: float
    estimated_memory_strength: float
    weighted_success_ratio: float
    forgetting_curve_decay_per_day: float
    history_window_size: int
    last_reviewed_at: Optional[Timestamp]
    last_review_result: Optional[RecallPointReviewResult]
    review_count: int
    history: Tuple[RecallPointReviewHistoryItem, ...]
