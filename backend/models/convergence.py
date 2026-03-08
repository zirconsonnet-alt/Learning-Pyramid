from dataclasses import dataclass
from typing import Tuple

from backend.models.enums import ConvergenceState
from backend.models.errors import PreconditionFailure
from backend.models.types import (
    ConvergenceId,
    ConvergenceRuleId,
    ProjectId,
    RangeId,
    ReviewTaskId,
)


@dataclass(frozen=True, slots=True)
class Convergence:
    """
    3.2 Convergence：轮次递推生成器（生成 ReviewTask 的本地语义，不绑定系统调度）
    """

    project_id: ProjectId
    convergence_id: ConvergenceId
    seed_range_id: RangeId
    rule_id: ConvergenceRuleId
    review_task_ids: Tuple[ReviewTaskId, ...]
    state: ConvergenceState

    def validate_local_invariants(self) -> None:
        if not str(self.convergence_id):
            raise PreconditionFailure("Convergence.convergence_id must be non-empty")
        if not str(self.seed_range_id):
            raise PreconditionFailure("Convergence.seed_range_id must be non-empty")
        if not str(self.rule_id):
            raise PreconditionFailure("Convergence.rule_id must be non-empty")
        for rid in self.review_task_ids:
            if not str(rid):
                raise PreconditionFailure("Convergence.review_task_ids contains empty id")
        if self.state not in (ConvergenceState.IN_PROGRESS, ConvergenceState.TERMINATED):
            raise PreconditionFailure(f"Unknown Convergence.state: {self.state}")

    @property
    def round_count(self) -> int:
        return len(self.review_task_ids)

