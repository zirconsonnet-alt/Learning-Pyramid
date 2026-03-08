from typing import Optional, Sequence, Tuple

from backend.models.errors import NotFound, PreconditionFailure
from backend.models.types import RangeId, RecallPointId, ReviewTaskId

from .interfaces import (
    MutationSession,
    RangeSnapshotRepository,
    RecallPointRepository,
    ReviewSubmitBinaryResult,
    ReviewTaskRepository,
)


def review_submit_binary(
    *,
    session: MutationSession,
    review_task_repo: ReviewTaskRepository,
    range_snapshot_repo: RangeSnapshotRepository,
    recall_point_repo: RecallPointRepository,
    review_task_id: ReviewTaskId,
    can_recall: Sequence[int],
) -> ReviewSubmitBinaryResult:
    """
    2.2 协议：复习提交（Review Submit, Binary）

    关键强约束对齐：
    - 任一 get 的 NotFound 对外统一映射为 PreconditionFailure
    - can_recall 非空；元素必须是 0/1；长度必须与 rp_ids 一致
    - 协议前置条件：rp_ids 中每个 RecallPointId 必须可解析（在任何 staged 写入之前完成）
    - focus_rp_ids 保序；为空则 result_range_id=None；非空则 intern(tuple(focus_rp_ids))
    """

    # ---- Precondition checks that don't touch repositories ----
    if can_recall is None or len(can_recall) == 0:
        raise PreconditionFailure("can_recall must be non-empty")
    for i, v in enumerate(can_recall):
        if v not in (0, 1):
            raise PreconditionFailure(f"can_recall[{i}] must be 0 or 1, got {v}")

    # ---- Read-set (NotFound -> PreconditionFailure) ----
    try:
        review_task = review_task_repo.get(session, review_task_id)
    except NotFound:
        raise PreconditionFailure(f"review_task_id not resolvable: {review_task_id}")

    input_range_id = getattr(review_task, "input_range_id", None)
    if input_range_id is None:
        raise PreconditionFailure("ReviewTask missing required field: input_range_id")

    try:
        input_snapshot = range_snapshot_repo.get(session, input_range_id)
    except NotFound:
        raise PreconditionFailure(f"input_range_id not resolvable: {input_range_id}")

    rp_ids: Tuple[RecallPointId, ...] = tuple(input_snapshot.recall_point_ids)

    if len(can_recall) != len(rp_ids):
        raise PreconditionFailure(
            f"len(can_recall) != len(rp_ids): {len(can_recall)} != {len(rp_ids)}"
        )

    for idx, rp_id in enumerate(rp_ids):
        try:
            recall_point_repo.get(session, rp_id)
        except NotFound:
            raise PreconditionFailure(f"rp_ids[{idx}] not resolvable: {rp_id}")

    focus_rp_ids: list[RecallPointId] = []
    for i, rp_id in enumerate(rp_ids):
        if can_recall[i] == 0:
            focus_rp_ids.append(rp_id)

    if len(focus_rp_ids) == 0:
        result_range_id: Optional[RangeId] = None
    else:
        result_range_id = range_snapshot_repo.intern(session, tuple(focus_rp_ids))

    return ReviewSubmitBinaryResult(
        review_task_id=review_task_id,
        result_range_id=result_range_id,
        focus_rp_ids=tuple(focus_rp_ids),
    )

