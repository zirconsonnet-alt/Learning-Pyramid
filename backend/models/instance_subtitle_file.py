from dataclasses import dataclass

from backend.models.errors import PreconditionFailure
from backend.models.types import InstanceId, ProjectId, Timestamp, now_utc_ms


INSTANCE_SUBTITLE_SOURCE_UPLOADED = "UPLOADED"
SUPPORTED_INSTANCE_SUBTITLE_SOURCES = frozenset({INSTANCE_SUBTITLE_SOURCE_UPLOADED})


@dataclass(frozen=True, slots=True)
class InstanceSubtitleSegment:
    start_ms: int
    end_ms: int
    text: str

    def validate(self) -> None:
        if int(self.start_ms) < 0:
            raise PreconditionFailure("InstanceSubtitleSegment.start_ms must be >= 0")
        if int(self.end_ms) <= int(self.start_ms):
            raise PreconditionFailure("InstanceSubtitleSegment.end_ms must be greater than start_ms")
        if not str(self.text or "").strip():
            raise PreconditionFailure("InstanceSubtitleSegment.text must be non-empty")


@dataclass(frozen=True, slots=True)
class InstanceSubtitleFile:
    project_id: ProjectId
    instance_id: InstanceId
    file_name: str
    format: str
    source: str
    segments: tuple[InstanceSubtitleSegment, ...]
    updated_at: Timestamp

    @classmethod
    def create(
        cls,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        file_name: str,
        format: str,
        source: str = INSTANCE_SUBTITLE_SOURCE_UPLOADED,
        segments: tuple[InstanceSubtitleSegment, ...],
        updated_at: Timestamp | None = None,
    ) -> "InstanceSubtitleFile":
        item = cls(
            project_id=project_id,
            instance_id=instance_id,
            file_name=str(file_name or "").strip(),
            format=str(format or "").strip().lower(),
            source=str(source or "").strip(),
            segments=tuple(segments),
            updated_at=updated_at or now_utc_ms(),
        )
        item.validate_write_time()
        return item

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("InstanceSubtitleFile.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("InstanceSubtitleFile.instance_id must be non-empty")
        if not self.file_name:
            raise PreconditionFailure("InstanceSubtitleFile.file_name must be non-empty")
        if self.format not in {"srt", "vtt", "ass", "ssa"}:
            raise PreconditionFailure("InstanceSubtitleFile.format is unsupported")
        if self.source not in SUPPORTED_INSTANCE_SUBTITLE_SOURCES:
            raise PreconditionFailure("InstanceSubtitleFile.source is unsupported")
        if not self.segments:
            raise PreconditionFailure("InstanceSubtitleFile.segments must be non-empty")
        for segment in self.segments:
            segment.validate()
        if self.updated_at is None:
            raise PreconditionFailure("InstanceSubtitleFile.updated_at must be provided")
