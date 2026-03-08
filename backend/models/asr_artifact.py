from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from backend.models.enums import AsrProvider
from backend.models.errors import PreconditionFailure
from backend.models.types import AsrArtifactId, InstanceId, ProjectId, RecallPointId, Timestamp


@dataclass(frozen=True, slots=True)
class AsrSegment:
    start_ms: int
    end_ms: int
    text: str
    confidence: Optional[float] = None

    def validate_write_time(self) -> None:
        if int(self.start_ms) < 0 or int(self.end_ms) < 0:
            raise PreconditionFailure("AsrSegment.start_ms/end_ms must be >= 0")
        if int(self.end_ms) < int(self.start_ms):
            raise PreconditionFailure("AsrSegment.end_ms must be >= start_ms")
        if self.text is None:
            raise PreconditionFailure("AsrSegment.text must be provided")
        if self.confidence is not None:
            c = float(self.confidence)
            if not (0.0 <= c <= 1.0):
                raise PreconditionFailure("AsrSegment.confidence must be within [0,1]")


@dataclass(frozen=True, slots=True)
class AsrArtifact:
    project_id: ProjectId
    asr_artifact_id: AsrArtifactId
    created_at: Timestamp
    provider: AsrProvider
    recall_point_id: RecallPointId
    source_instance_id: InstanceId
    center_ms: int
    pre_ms: int
    post_ms: int
    segments: Tuple[AsrSegment, ...] = field(default_factory=tuple)

    def cache_key(self) -> tuple[str, str, int, int, int]:
        return (str(self.recall_point_id), str(self.provider.value), int(self.center_ms), int(self.pre_ms), int(self.post_ms))

    def validate_write_time(self) -> None:
        if not str(self.project_id):
            raise PreconditionFailure("AsrArtifact.project_id must be non-empty")
        if not str(self.asr_artifact_id):
            raise PreconditionFailure("AsrArtifact.asr_artifact_id must be non-empty")
        if self.created_at is None:
            raise PreconditionFailure("AsrArtifact.created_at must be provided")
        if not isinstance(self.provider, AsrProvider):
            raise PreconditionFailure("AsrArtifact.provider must be AsrProvider")
        if not str(self.recall_point_id):
            raise PreconditionFailure("AsrArtifact.recall_point_id must be non-empty")
        if not str(self.source_instance_id):
            raise PreconditionFailure("AsrArtifact.source_instance_id must be non-empty")
        if int(self.pre_ms) < 0 or int(self.post_ms) < 0:
            raise PreconditionFailure("AsrArtifact.pre_ms/post_ms must be >= 0")
        for seg in self.segments:
            seg.validate_write_time()

