from dataclasses import dataclass
from typing import Optional

from .enums import MistakeStatus, RecallPointState
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
    anchor: Optional[Anchor] = None
    references: tuple[RecallPointId, ...] = tuple()
    insights: tuple[RichContent, ...] = tuple()
    source_project_id: Optional[ProjectId] = None
    source_recall_point_id: Optional[RecallPointId] = None
    source_material_id: Optional[str] = None
    source_material_title: Optional[str] = None
    source_anchor_label: Optional[str] = None
    mistake_status: Optional[MistakeStatus] = None
    mistake_note: Optional[str] = None
    state: RecallPointState = RecallPointState.ACTIVE
    deleted_at: Optional[Timestamp] = None

    def validate_write_time(self) -> None:
        # 1.4.3 写前条件
        if not str(self.recall_point_id):
            raise PreconditionFailure("RecallPoint.recall_point_id must be non-empty")
        if self.created_at is None:
            raise PreconditionFailure("RecallPoint.created_at must be provided")
        if self.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("RecallPoint.state must be ACTIVE on write")
        if self.deleted_at is not None:
            raise PreconditionFailure("RecallPoint.deleted_at must be None on write")
        validate_rich_content_write_time(self.question)
        validate_rich_content_write_time(self.answer)
        if self.anchor is not None:
            self.anchor.validate_write_time()
        seen_references: set[str] = set()
        for reference in self.references:
            key = str(reference).strip()
            if not key:
                raise PreconditionFailure("RecallPoint.references must contain non-empty RecallPointId")
            if key == str(self.recall_point_id):
                raise PreconditionFailure("RecallPoint.references must not contain self")
            if key in seen_references:
                raise PreconditionFailure("RecallPoint.references must not contain duplicates")
            seen_references.add(key)
        for ins in self.insights:
            validate_rich_content_write_time(ins)
        if (self.source_project_id is None) != (self.source_recall_point_id is None):
            raise PreconditionFailure(
                "RecallPoint.source_project_id and RecallPoint.source_recall_point_id must be provided together"
            )
        if self.source_material_id is not None and not str(self.source_material_id).strip():
            raise PreconditionFailure("RecallPoint.source_material_id must be non-empty when provided")
        if self.source_material_title is not None and not str(self.source_material_title).strip():
            raise PreconditionFailure("RecallPoint.source_material_title must be non-empty when provided")
        if self.source_anchor_label is not None and not str(self.source_anchor_label).strip():
            raise PreconditionFailure("RecallPoint.source_anchor_label must be non-empty when provided")
        if self.mistake_status is not None and not isinstance(self.mistake_status, MistakeStatus):
            raise PreconditionFailure("RecallPoint.mistake_status must be MistakeStatus when provided")
        if self.mistake_note is not None and len(str(self.mistake_note)) > 2000:
            raise PreconditionFailure("RecallPoint.mistake_note must be <= 2000 chars")

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
