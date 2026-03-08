from dataclasses import dataclass

from .errors import PreconditionFailure
from .rich_content import RichContent, validate_rich_content_write_time
from .types import InstanceId, ProjectId, RecallPointId, Timestamp


@dataclass(frozen=True, slots=True)
class Anchor:
    instance_id: InstanceId
    position: str

    def validate_write_time(self) -> None:
        # 1.3.1：instance_id 非空；position 非空
        if not str(self.instance_id):
            raise PreconditionFailure("Anchor.instance_id must be non-empty")
        if not self.position or not self.position.strip():
            raise PreconditionFailure("Anchor.position must be non-empty")

    def anchor_repr(self) -> str:
        # 1.3.1 派生字段
        return f"{self.instance_id}:{self.position}"


@dataclass(frozen=True, slots=True)
class RecallPoint:
    project_id: ProjectId
    recall_point_id: RecallPointId
    created_at: Timestamp
    question: RichContent
    answer: RichContent
    anchor: Anchor
    insights: tuple[RichContent, ...] = tuple()

    def validate_write_time(self) -> None:
        # 1.4.3 写前条件
        if not str(self.recall_point_id):
            raise PreconditionFailure("RecallPoint.recall_point_id must be non-empty")
        if self.created_at is None:
            raise PreconditionFailure("RecallPoint.created_at must be provided")
        validate_rich_content_write_time(self.question)
        validate_rich_content_write_time(self.answer)
        if self.anchor is None:
            raise PreconditionFailure("RecallPoint.anchor must be provided")
        self.anchor.validate_write_time()
        for ins in self.insights:
            validate_rich_content_write_time(ins)

    def __str__(self) -> str:
        # 1.4.1 派生字段：简单 Q/A 可读表示
        def render(rc: RichContent) -> str:
            parts: list[str] = []
            for b in rc:
                if getattr(b, "kind", None) is None:
                    continue
                if b.kind.value == "TEXT":
                    parts.append((b.text or "").strip().replace("\n", " "))
                elif b.kind.value == "IMAGE":
                    parts.append("[IMAGE]")
            s = " ".join([p for p in parts if p])
            return s if s else "[RichContent]"

        q = render(self.question)
        a = render(self.answer)
        return f"Q: {q} | A: {a}"
