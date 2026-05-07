from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Tuple

from backend.models.errors import PreconditionFailure
from backend.models.types import InstanceId, ProjectId, Timestamp


VideoWatchRange = Tuple[int, int]


def normalize_video_watch_ranges(
    ranges: Iterable[VideoWatchRange],
    *,
    duration_ms: int | None = None,
) -> Tuple[VideoWatchRange, ...]:
    max_ms = int(duration_ms) if duration_ms is not None and int(duration_ms) > 0 else None
    cleaned: list[VideoWatchRange] = []
    for start_ms, end_ms in ranges:
        start = max(0, int(start_ms))
        end = max(0, int(end_ms))
        if max_ms is not None:
            start = min(start, max_ms)
            end = min(end, max_ms)
        if end > start:
            cleaned.append((start, end))

    cleaned.sort(key=lambda item: item[0])
    if not cleaned:
        return tuple()

    merged: list[VideoWatchRange] = [cleaned[0]]
    for start, end in cleaned[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


def sum_video_watch_ranges(ranges: Iterable[VideoWatchRange]) -> int:
    return sum(max(0, int(end_ms) - int(start_ms)) for start_ms, end_ms in ranges)


@dataclass(frozen=True, slots=True)
class VideoWatchProgress:
    project_id: ProjectId
    instance_id: InstanceId
    duration_ms: int | None
    ranges: Tuple[VideoWatchRange, ...]
    completed_at: Timestamp | None
    updated_at: Timestamp

    @property
    def watched_ms(self) -> int:
        watched = sum_video_watch_ranges(self.ranges)
        if self.duration_ms is not None and self.duration_ms > 0:
            return min(int(self.duration_ms), watched)
        return watched

    @staticmethod
    def create(
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        duration_ms: int | None = None,
        ranges: Iterable[VideoWatchRange] = tuple(),
        completed_at: Timestamp | None = None,
        updated_at: Timestamp,
    ) -> "VideoWatchProgress":
        normalized_duration = None if duration_ms is None or int(duration_ms) <= 0 else int(duration_ms)
        item = VideoWatchProgress(
            project_id=project_id,
            instance_id=instance_id,
            duration_ms=normalized_duration,
            ranges=normalize_video_watch_ranges(ranges, duration_ms=normalized_duration),
            completed_at=completed_at,
            updated_at=updated_at,
        )
        item.validate_write_time()
        return item

    def with_range(
        self,
        *,
        start_ms: int,
        end_ms: int,
        duration_ms: int | None,
        updated_at: Timestamp,
    ) -> "VideoWatchProgress":
        next_duration = self.duration_ms
        if duration_ms is not None and int(duration_ms) > 0:
            next_duration = max(int(duration_ms), int(next_duration or 0))
        return VideoWatchProgress.create(
            self.project_id,
            self.instance_id,
            duration_ms=next_duration,
            ranges=(*self.ranges, (int(start_ms), int(end_ms))),
            completed_at=self.completed_at,
            updated_at=updated_at,
        )

    def with_completed(self, *, duration_ms: int, completed_at: Timestamp) -> "VideoWatchProgress":
        if int(duration_ms) <= 0:
            raise PreconditionFailure("duration_ms must be positive when marking video completed")
        return VideoWatchProgress.create(
            self.project_id,
            self.instance_id,
            duration_ms=int(duration_ms),
            ranges=((0, int(duration_ms)),),
            completed_at=completed_at,
            updated_at=completed_at,
        )

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("VideoWatchProgress.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("VideoWatchProgress.instance_id must be non-empty")
        if self.duration_ms is not None and int(self.duration_ms) <= 0:
            raise PreconditionFailure("VideoWatchProgress.duration_ms must be positive when present")
        if not isinstance(self.updated_at, datetime):
            raise PreconditionFailure("VideoWatchProgress.updated_at must be datetime")
        if self.completed_at is not None and not isinstance(self.completed_at, datetime):
            raise PreconditionFailure("VideoWatchProgress.completed_at must be datetime")
        if normalize_video_watch_ranges(self.ranges, duration_ms=self.duration_ms) != self.ranges:
            raise PreconditionFailure("VideoWatchProgress.ranges must be normalized")
