from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class DesktopAgentMetricSample:
    project_id: str
    bucket_start: str
    bucket_seconds: int
    captured_at: str
    session_count: int
    active_stream_count: int
    completed_stream_count: int
    failed_stream_count: int
    cancelled_stream_count: int
    bytes_from_agent_total: int
    bytes_to_viewer_total: int
    hls_job_count: int
    active_hls_job_count: int
    completed_hls_job_count: int
    failed_hls_job_count: int
    cancelled_hls_job_count: int
    hls_artifact_bytes_total: int
    hls_cache_entry_count: int
    hls_cache_bytes: int

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("DesktopAgentMetricSample.project_id must be non-empty")
        if not str(self.bucket_start).strip():
            raise PreconditionFailure("DesktopAgentMetricSample.bucket_start must be non-empty")
        if int(self.bucket_seconds) <= 0:
            raise PreconditionFailure("DesktopAgentMetricSample.bucket_seconds must be > 0")
        if not str(self.captured_at).strip():
            raise PreconditionFailure("DesktopAgentMetricSample.captured_at must be non-empty")
        for field_name in (
            "session_count",
            "active_stream_count",
            "completed_stream_count",
            "failed_stream_count",
            "cancelled_stream_count",
            "bytes_from_agent_total",
            "bytes_to_viewer_total",
            "hls_job_count",
            "active_hls_job_count",
            "completed_hls_job_count",
            "failed_hls_job_count",
            "cancelled_hls_job_count",
            "hls_artifact_bytes_total",
            "hls_cache_entry_count",
            "hls_cache_bytes",
        ):
            if int(getattr(self, field_name)) < 0:
                raise PreconditionFailure(f"DesktopAgentMetricSample.{field_name} must be >= 0")
