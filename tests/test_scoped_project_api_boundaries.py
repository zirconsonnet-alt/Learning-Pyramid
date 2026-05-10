import unittest
from dataclasses import dataclass
from pathlib import Path

from backend.models.errors import PreconditionFailure
from backend.system.api import MAX_ASR_UPLOAD_BYTES
from backend.system.auth_store import AuthUser
from backend.system.runtime_features import RuntimeFeatures


class RequestBodyShouldNotBeRead:
    def __init__(self, content_length: int, content_type: str = "image/png") -> None:
        self.headers = {
            "content-length": str(content_length),
            "content-type": content_type,
        }

    async def body(self) -> bytes:
        raise AssertionError("request body should not be read after Content-Length rejection")


class UploadBoundariesTest(unittest.IsolatedAsyncioTestCase):
    async def test_image_upload_rejects_oversized_content_length_before_reading_body(self) -> None:
        from adapter.routers.media import MAX_IMAGE_UPLOAD_BYTES, upload_media_asset

        with self.assertRaises(PreconditionFailure):
            await upload_media_asset(
                RequestBodyShouldNotBeRead(MAX_IMAGE_UPLOAD_BYTES + 1),
                project=None,  # type: ignore[arg-type]
                api=None,  # type: ignore[arg-type]
            )

    async def test_asr_upload_rejects_oversized_content_length_before_reading_file(self) -> None:
        from adapter.routers.asr import reject_oversized_asr_upload

        with self.assertRaises(PreconditionFailure):
            reject_oversized_asr_upload(MAX_ASR_UPLOAD_BYTES + 1)


class AuthOwnershipStore:
    def __init__(self) -> None:
        self.project_ids = {"subj_000001"}
        self.added: list[tuple[str, str]] = []

    def list_project_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        return tuple(sorted(self.project_ids))

    def add_project_owner(self, project_id: str, user_id: str) -> None:
        self.added.append((str(project_id), str(user_id)))


class ApiWithScopedResolution:
    def resolve_scoped_project_internal_key(self, subject_id: str, project_id: str) -> str:
        self.resolved = (subject_id, project_id)
        return "proj_internal_000001"


class RequestState:
    pass


class RequestWithUser:
    def __init__(self) -> None:
        self.state = RequestState()
        self.state.auth_user = AuthUser(
            user_id="user_1",
            email="user@example.com",
            created_at="2026-05-10T00:00:00+00:00",
            public_uid="u000001",
            nickname="User",
            bio="",
            avatar_key=None,
            status="ACTIVE",
            updated_at="2026-05-10T00:00:00+00:00",
        )


def hosted_features() -> RuntimeFeatures:
    return RuntimeFeatures(
        app_mode="hosted",
        asr_enabled=True,
        server_media_stream_enabled=False,
        browser_local_media_enabled=True,
        baidu_netdisk_enabled=False,
        auth_enabled=True,
        allow_signup=False,
        signup_invite_required=True,
        data_safety_storage_checks_enabled=False,
    )


class ScopedAuthBoundaryTest(unittest.TestCase):
    def test_resolve_scoped_project_does_not_store_internal_project_ownership(self) -> None:
        from adapter import scoped_projects

        original_features = scoped_projects.current_runtime_features
        scoped_projects.current_runtime_features = hosted_features
        auth_store = AuthOwnershipStore()
        try:
            project = scoped_projects.resolve_scoped_project(
                "subj_000001",
                "proj_000001",
                RequestWithUser(),  # type: ignore[arg-type]
                api=ApiWithScopedResolution(),  # type: ignore[arg-type]
                auth_store=auth_store,  # type: ignore[arg-type]
            )
        finally:
            scoped_projects.current_runtime_features = original_features

        self.assertEqual("proj_internal_000001", project.internal_project_id)
        self.assertEqual([], auth_store.added)


class RawLlmScopedRouteTest(unittest.TestCase):
    def test_scoped_raw_llm_chat_is_rejected(self) -> None:
        from adapter.routers.system import reject_scoped_raw_llm_chat

        with self.assertRaises(PreconditionFailure):
            reject_scoped_raw_llm_chat()


class MediaBoundaryApi:
    def __init__(self) -> None:
        self.listed_project_id: str | None = None
        self.stream_request: tuple[str, str] | None = None

    def list_instances_with_media_summary(self, project_id: str) -> tuple[dict[str, object], ...]:
        self.listed_project_id = project_id
        from backend.models.enums import InstancePresence
        from backend.models.instance import Instance
        from backend.models.types import InstanceId, ProjectId

        return (
            MediaSummaryFixture(
                instance=Instance.create(
                    ProjectId("internal_1"),
                    InstanceId("inst_1"),
                    "video.mp4",
                    presence=InstancePresence.PRESENT,
                ),
                media_source_kind="SERVER_FS",
                playback_kind="FILE",
                duration_ms=1200,
            ),
        )

    def resolve_instance_media_file_path(self, project_id: str, instance_id: str) -> Path:
        self.stream_request = (project_id, instance_id)
        return Path(__file__).resolve()


@dataclass(frozen=True)
class MediaSummaryFixture:
    instance: object
    media_source_kind: str
    playback_kind: str
    duration_ms: int | None


class ScopedSubjectContextApi:
    def __init__(self) -> None:
        self.requested_project_id: str | None = None

    def get_scoped_subject_context_for_project(self, project_id: str, *, public_project_id: str) -> dict[str, object]:
        self.requested_project_id = project_id
        from backend.models.enums import ProjectState
        from backend.models.project import Project
        from backend.models.study_material import StudyMaterial, StudyMaterialType
        from backend.models.types import ProjectId, now_utc_ms

        created_at = now_utc_ms()
        subject = Project(
            project_id=ProjectId("subj_1"),
            title="Subject",
            state=ProjectState.ACTIVE,
            created_at=created_at,
        )
        material = StudyMaterial(
            subject_id=ProjectId("subj_1"),
            material_id="mat_1",
            material_type=StudyMaterialType.COURSE,
            title="Material",
            created_at=created_at,
            project_id=ProjectId(public_project_id),
            internal_project_key=ProjectId(project_id),
        )
        return {
            "subject": subject,
            "current_material": material,
            "materials": (material,),
            "current_project_id": public_project_id,
            "current_internal_project_key": project_id,
        }


class RouterBoundaryTest(unittest.TestCase):
    def test_list_instances_uses_public_media_summary_boundary(self) -> None:
        from adapter.routers.materials import list_instances
        from adapter.scoped_projects import ScopedProject

        api = MediaBoundaryApi()
        response = list_instances(ScopedProject("subj_1", "proj_1", "internal_1"), api=api)  # type: ignore[arg-type]

        self.assertEqual("internal_1", api.listed_project_id)
        self.assertEqual(
            {
                "instanceId": "inst_1",
                "materialId": "video.mp4",
                "materialDisplayName": "video.mp4",
                "presence": "PRESENT",
                "lastSeenAt": None,
                "mediaSourceKind": "SERVER_FS",
                "playbackKind": "FILE",
                "durationMs": 1200,
            },
            response["data"][0],
        )

    def test_stream_instance_media_uses_public_file_path_boundary(self) -> None:
        from adapter.routers.media import stream_instance_media
        from adapter.scoped_projects import ScopedProject

        api = MediaBoundaryApi()
        response = stream_instance_media("inst_1", ScopedProject("subj_1", "proj_1", "internal_1"), api=api)  # type: ignore[arg-type]

        self.assertEqual(("internal_1", "inst_1"), api.stream_request)
        self.assertEqual(str(Path(__file__).resolve()), response.path)

    def test_subject_context_route_uses_resolved_scoped_project(self) -> None:
        from adapter.routers.projects import get_scoped_project_subject_context
        from adapter.scoped_projects import ScopedProject

        api = ScopedSubjectContextApi()
        response = get_scoped_project_subject_context(ScopedProject("subj_1", "proj_1", "internal_1"), api=api)  # type: ignore[arg-type]

        self.assertEqual("internal_1", api.requested_project_id)
        self.assertEqual("proj_1", response["data"]["currentProjectId"])


if __name__ == "__main__":
    unittest.main()
