from typing import Sequence

from backend.models.errors import NotFound, PreconditionFailure
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskLeaf
from backend.models.recall_point import RecallPoint
from backend.models.rich_content import RichContent, validate_rich_content_write_time
from backend.models.types import now_utc_ms

from .interfaces import (
    InstanceRepository,
    LearningItem,
    LearningTaskNodeRepository,
    LearningTaskRepository,
    LearningTaskSubmitResult,
    MutationSession,
    ProtocolIdGenerator,
    RecallPointRepository,
)


def learning_task_submit(
    *,
    session: MutationSession,
    id_gen: ProtocolIdGenerator,
    instance_repo: InstanceRepository,
    recall_point_repo: RecallPointRepository,
    learning_task_repo: LearningTaskRepository,
    learning_task_node_repo: LearningTaskNodeRepository,
    items: Sequence[LearningItem],
    title: str,
    entry_node_title: str | None = None,
) -> LearningTaskSubmitResult:
    """
    2.1 协议：学习任务提交（LearningTask Submit）

    强约束对齐：
    - items 非空、title 非空
    - 锚点是否必填/可解析由上层项目类型规则决定；本协议只接受已完成规则校验的 items
    - NotFound 统一映射为 PreconditionFailure
    - 写入产物：RecallPoint* + LearningTask + LearningTaskNode(leaf)
    """

    # ---- Precondition checks (MUST happen before any staged writes) ----
    if not items or len(items) == 0:
        raise PreconditionFailure("LearningTaskSubmit.items must be non-empty")
    if title is None or not str(title).strip():
        raise PreconditionFailure("LearningTaskSubmit.title must be non-empty")

    # 逐项校验输入；锚点是否存在与 instance 可解析性由上层规则先行保证。
    # 重要：在任何 repo.add() 之前完成，确保失败不产生 staged 写入（0b.5）
    for idx, it in enumerate(items):
        if it.question is None:
            raise PreconditionFailure(f"items[{idx}].question must be provided")
        if it.answer is None:
            raise PreconditionFailure(f"items[{idx}].answer must be provided")
        validate_rich_content_write_time(it.question)
        validate_rich_content_write_time(it.answer)
        if it.anchor is not None:
            it.anchor.validate_write_time()
            try:
                instance_repo.get(session, it.anchor.instance_id)
            except NotFound:
                raise PreconditionFailure(
                    f"items[{idx}].anchor.instance_id not resolvable: {it.anchor.instance_id}"
                )

    # ---- Writes (staged) ----
    project_id = session.project_id

    recall_point_ids: list = []
    for it in items:
        rp_id = id_gen.new_recall_point_id(project_id)
        rp = RecallPoint(
            project_id=project_id,
            recall_point_id=rp_id,
            created_at=now_utc_ms(),
            question=it.question,
            answer=it.answer,
            anchor=it.anchor,
        )
        rp.validate_write_time()
        recall_point_repo.add(session, rp)
        recall_point_ids.append(rp_id)

    learning_task_id = id_gen.new_learning_task_id(project_id)
    task = LearningTask(
        project_id=project_id,
        learning_task_id=learning_task_id,
        recall_point_ids=tuple(recall_point_ids),
        title=title,
    )
    task.validate_write_time()
    learning_task_repo.add(session, task)

    entry_node_id = id_gen.new_learning_task_node_id(project_id)
    node_title = entry_node_title if (entry_node_title and entry_node_title.strip()) else title
    entry_node = LearningTaskLeaf(
        project_id=project_id,
        node_id=entry_node_id,
        parent_id=None,
        bound_learning_task_id=learning_task_id,
        title=node_title,
    )
    entry_node.validate_write_time()
    learning_task_node_repo.add(session, entry_node)

    return LearningTaskSubmitResult(
        learning_task_id=learning_task_id,
        entry_node_id=entry_node_id,
        recall_point_ids=tuple(recall_point_ids),
    )
