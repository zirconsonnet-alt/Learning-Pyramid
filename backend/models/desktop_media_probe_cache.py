from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class DesktopMediaProbeCache:
    project_id: str
    instance_id: str
    agent_id: str
    container: str
    video_codec: str | None
    audio_codec: str | None
    duration_ms: int | None
    bitrate_bps: int | None
    width: int | None
    height: int | None
    updated_at: str
    fps: float | None = None
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    video_stream_count: int | None = None
    audio_stream_count: int | None = None
    subtitle_stream_count: int | None = None
    size_bytes: int | None = None
    modified_at: str | None = None

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("DesktopMediaProbeCache.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("DesktopMediaProbeCache.instance_id must be non-empty")
        if not str(self.agent_id).strip():
            raise PreconditionFailure("DesktopMediaProbeCache.agent_id must be non-empty")
        if not str(self.container).strip():
            raise PreconditionFailure("DesktopMediaProbeCache.container must be non-empty")
        if self.duration_ms is not None and int(self.duration_ms) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.duration_ms must be >= 0 when provided")
        if self.bitrate_bps is not None and int(self.bitrate_bps) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.bitrate_bps must be >= 0 when provided")
        if self.width is not None and int(self.width) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.width must be >= 0 when provided")
        if self.height is not None and int(self.height) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.height must be >= 0 when provided")
        if self.fps is not None and float(self.fps) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.fps must be >= 0 when provided")
        if self.audio_channels is not None and int(self.audio_channels) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.audio_channels must be >= 0 when provided")
        if self.audio_sample_rate is not None and int(self.audio_sample_rate) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.audio_sample_rate must be >= 0 when provided")
        if self.video_stream_count is not None and int(self.video_stream_count) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.video_stream_count must be >= 0 when provided")
        if self.audio_stream_count is not None and int(self.audio_stream_count) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.audio_stream_count must be >= 0 when provided")
        if self.subtitle_stream_count is not None and int(self.subtitle_stream_count) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.subtitle_stream_count must be >= 0 when provided")
        if self.size_bytes is not None and int(self.size_bytes) < 0:
            raise PreconditionFailure("DesktopMediaProbeCache.size_bytes must be >= 0 when provided")
        if not str(self.updated_at).strip():
            raise PreconditionFailure("DesktopMediaProbeCache.updated_at must be non-empty")
