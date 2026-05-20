from typing import Any

import pytest

from adapter.routers.materials import import_learning_objects_from_baidu_netdisk
from adapter.schemas import ImportLearningObjectsFromBaiduNetdiskRequest
from adapter.scoped_projects import ScopedProject
from backend.models.cloud_account_binding import CloudAccountBinding
from backend.models.enums import InstancePresence, MaterialSourceKind, ProjectType
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf
from backend.models.enums import SessionMode
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthUser
from backend.system.baidu_netdisk_client import BAIDU_NETDISK_PROVIDER, BaiduNetdiskFileItem
from backend.system.baidu_netdisk_client import BaiduNetdiskClient
from backend.system.auth_store import SQLiteAuthStore
from backend.system.inmemory_system import InMemorySystem


class _JsonResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.url = "https://pan.baidu.com/rest/2.0/xpan/file"
        self.text = ""
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_list_files_requests_full_entries_and_parses_directories(monkeypatch) -> None:
    requests: list[dict[str, Any]] = []

    def fake_request(
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        timeout: int,
        allow_redirects: bool,
    ) -> _JsonResponse:
        requests.append(
            {
                "method": method,
                "url": url,
                "params": dict(params),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        return _JsonResponse(
            {
                "errno": 0,
                "has_more": 0,
                "list": [
                    {
                        "fs_id": 1001,
                        "path": "/课程/第一章",
                        "server_filename": "第一章",
                        "isdir": 1,
                    },
                    {
                        "fs_id": 1002,
                        "path": "/课程/导论.mp4",
                        "server_filename": "导论.mp4",
                        "isdir": 0,
                        "category": 1,
                        "size": 1024,
                    },
                ],
            }
        )

    monkeypatch.setattr("backend.system.baidu_netdisk_client.requests.request", fake_request)

    items, has_more = BaiduNetdiskClient().list_files("access-token", dir_path="/课程", page=2, limit=50)

    assert has_more is False
    assert requests[0]["params"]["dir"] == "/课程"
    assert requests[0]["params"]["start"] == 50
    assert requests[0]["params"]["limit"] == 50
    assert requests[0]["params"]["folder"] == 0
    assert requests[0]["params"]["access_token"] == "access-token"
    assert items[0].is_dir is True
    assert items[0].name == "第一章"
    assert items[1].is_dir is False
    assert items[1].mime_type == "video/mp4"
    assert items[1].category == 1


class _CloudAccountStore:
    account = CloudAccountBinding.create(
        account_id="account_1",
        user_id="user_1",
        provider=BAIDU_NETDISK_PROVIDER,
        provider_user_id="baidu-user",
        display_name="百度账号",
        avatar_url=None,
        access_token_ciphertext="ciphertext",
        refresh_token_ciphertext="refresh-ciphertext",
        expires_at=None,
        scope="basic,netdisk",
        meta={},
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    def get_user_cloud_account(
        self,
        user_id: str,
        *,
        account_id: str,
        provider: str | None = None,
        include_disabled: bool = False,
    ) -> CloudAccountBinding:
        assert user_id == self.account.user_id
        assert account_id == self.account.account_id
        assert provider in (None, self.account.provider)
        assert include_disabled is False
        return self.account

    def get_cloud_account_by_id(self, account_id: str, *, include_disabled: bool = False) -> CloudAccountBinding:
        assert account_id == self.account.account_id
        assert include_disabled is False
        return self.account


class _RequestState:
    pass


class _RequestWithUser:
    def __init__(self) -> None:
        self.state = _RequestState()
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


class _BaiduNetdiskImportRouterApi:
    def __init__(self) -> None:
        self.call: dict[str, Any] | None = None

    def import_learning_objects_from_baidu_netdisk(
        self,
        project_id: str,
        *,
        auth_store: object,
        user_id: str,
        account_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.call = {
            "project_id": project_id,
            "auth_store": auth_store,
            "user_id": user_id,
            "account_id": account_id,
            "items": items,
        }
        return {"imported_count": 1, "created_instances_count": 1}


def test_import_baidu_netdisk_router_serializes_items_with_pydantic_v1_dict() -> None:
    req = ImportLearningObjectsFromBaiduNetdiskRequest(
        accountId="account_1",
        items=[
            {
                "fileId": "file_1",
                "path": "/课程/导论.mp4",
                "name": "导论.mp4",
                "isDir": False,
                "sizeBytes": 1024,
                "mimeType": "video/mp4",
                "durationMs": 60000,
            }
        ],
    )
    auth_store = object()
    api = _BaiduNetdiskImportRouterApi()

    response = import_learning_objects_from_baidu_netdisk(
        req,
        _RequestWithUser(),  # type: ignore[arg-type]
        ScopedProject(subject_id="subj_1", scoped_project_id="proj_1", internal_project_id="internal_1"),
        api=api,  # type: ignore[arg-type]
        auth_store=auth_store,  # type: ignore[arg-type]
    )

    assert response == {"ok": True, "data": {"imported_count": 1, "created_instances_count": 1}}
    assert api.call is not None
    assert api.call["project_id"] == "internal_1"
    assert api.call["auth_store"] is auth_store
    assert api.call["user_id"] == "user_1"
    assert api.call["account_id"] == "account_1"
    assert api.call["items"] == [
        {
            "fileId": "file_1",
            "path": "/课程/导论.mp4",
            "name": "导论.mp4",
            "isDir": False,
            "sizeBytes": 1024,
            "mimeType": "video/mp4",
            "durationMs": 60000,
        }
    ]


def test_import_baidu_netdisk_folder_recursively_imports_videos(monkeypatch) -> None:
    api = SystemAPI(InMemorySystem())
    project_id = api.create_project(
        "Course",
        initial_source_kind=MaterialSourceKind.MANUAL,
        initial_project_type=ProjectType.COURSE,
    )
    calls: list[tuple[str, int]] = []
    items_by_dir = {
        "/课程": (
            BaiduNetdiskFileItem(
                file_id="dir-lesson",
                path="/课程/第一章",
                name="第一章",
                is_dir=True,
                size_bytes=None,
                mime_type=None,
                duration_ms=None,
                category=None,
                raw={},
            ),
            BaiduNetdiskFileItem(
                file_id="readme",
                path="/课程/readme.txt",
                name="readme.txt",
                is_dir=False,
                size_bytes=10,
                mime_type="text/plain",
                duration_ms=None,
                category=None,
                raw={},
            ),
        ),
        "/课程/第一章": (
            BaiduNetdiskFileItem(
                file_id="video-1",
                path="/课程/第一章/导论.mp4",
                name="导论.mp4",
                is_dir=False,
                size_bytes=1024,
                mime_type="video/mp4",
                duration_ms=60000,
                category=1,
                raw={},
            ),
            BaiduNetdiskFileItem(
                file_id="video-2",
                path="/课程/第一章/案例.mkv",
                name="案例.mkv",
                is_dir=False,
                size_bytes=2048,
                mime_type=None,
                duration_ms=None,
                category=None,
                raw={},
            ),
        ),
    }

    def fake_decrypt_secret_value(ciphertext: str) -> str:
        assert ciphertext == "ciphertext"
        return "access-token"

    def fake_list_files(access_token: str, *, dir_path: str = "/", page: int = 1, limit: int = 200):
        assert access_token == "access-token"
        assert limit == 200
        calls.append((dir_path, page))
        return items_by_dir.get(dir_path, ()), False

    monkeypatch.setattr("backend.system.instance_media.decrypt_secret_value", fake_decrypt_secret_value)
    monkeypatch.setattr(api._baidu_netdisk_client, "list_files", fake_list_files)

    result = api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=_CloudAccountStore(),  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "dir-course",
                "path": "/课程",
                "name": "课程",
                "isDir": True,
            }
        ],
    )

    assert result["imported_count"] == 2
    assert result["created_instances_count"] == 2
    assert result["marked_missing_count"] == 0
    assert result["replaced_learning_object_nodes_count"] == 4
    assert calls == [("/课程", 1), ("/课程/第一章", 1)]

    instances = {item.material_id.as_posix(): item for item in api.list_instances(project_id)}
    assert sorted(instances) == ["/课程/第一章/导论.mp4", "/课程/第一章/案例.mkv"]

    nodes = api.list_learning_object_nodes(project_id)
    containers = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectContainer)}
    leaves = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectLeaf)}
    assert containers["."].title == "课程"
    assert containers["第一章"].parent_id == containers["."].node_id
    assert sorted(leaves) == ["第一章/导论.mp4", "第一章/案例.mkv"]

    session = api.sys.begin_session(project_id, SessionMode.READ_ONLY)
    try:
        bindings = api.sys.instance_media_binding_repo.all(session)
    finally:
        api.sys.rollback(session)
    binding_paths = {binding.remote_path: binding for binding in bindings}
    assert binding_paths["/课程/第一章/导论.mp4"].remote_file_id == "video-1"
    assert binding_paths["/课程/第一章/导论.mp4"].playback_kind == "HLS"
    assert binding_paths["/课程/第一章/导论.mp4"].source_kind == MaterialSourceKind.BAIDU_NETDISK

    source_binding = api.get_project_material_source_binding(project_id)
    assert source_binding.source_kind == MaterialSourceKind.BAIDU_NETDISK
    assert source_binding.source_root_label == "课程"


def test_import_baidu_netdisk_replaces_learning_object_tree_and_prunes_unreferenced_absent_instances() -> None:
    api = SystemAPI(InMemorySystem())
    project_id = api.create_project(
        "Course",
        initial_source_kind=MaterialSourceKind.MANUAL,
        initial_project_type=ProjectType.COURSE,
    )
    auth_store = _CloudAccountStore()

    first_result = api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=auth_store,  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-1",
                "path": "/课程/第一章/导论.mp4",
                "name": "导论.mp4",
                "mimeType": "video/mp4",
                "durationMs": 60000,
            },
            {
                "fileId": "video-2",
                "path": "/课程/第一章/案例.mkv",
                "name": "案例.mkv",
                "mimeType": "video/x-matroska",
                "durationMs": 120000,
            },
        ],
    )

    assert first_result["imported_count"] == 2
    old_leaf_ids = {
        node.relative_path.as_posix(): node.node_id
        for node in api.list_learning_object_nodes(project_id)
        if isinstance(node, LearningObjectLeaf)
    }

    second_result = api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=auth_store,  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-3",
                "path": "/新课程/第二章/复盘.mp4",
                "name": "复盘.mp4",
                "mimeType": "video/mp4",
                "durationMs": 90000,
            }
        ],
    )

    assert second_result["imported_count"] == 1
    assert second_result["created_instances_count"] == 1
    assert second_result["marked_missing_count"] == 0
    assert second_result.get("deleted_instances_count") == 2
    assert second_result["replaced_learning_object_nodes_count"] == 2

    instances = {item.material_id.as_posix(): item for item in api.list_instances(project_id)}
    assert "/课程/第一章/导论.mp4" not in instances
    assert "/课程/第一章/案例.mkv" not in instances
    assert instances["/新课程/第二章/复盘.mp4"].presence == InstancePresence.PRESENT

    nodes = api.list_learning_object_nodes(project_id)
    containers = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectContainer)}
    leaves = {node.relative_path.as_posix(): node for node in nodes if isinstance(node, LearningObjectLeaf)}
    assert sorted(containers) == ["."]
    assert containers["."].title == "第二章"
    assert sorted(leaves) == ["复盘.mp4"]
    assert "第一章/导论.mp4" not in leaves
    assert "第一章/案例.mkv" not in leaves

    third_result = api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=auth_store,  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-1",
                "path": "/课程/第一章/导论.mp4",
                "name": "导论.mp4",
                "mimeType": "video/mp4",
                "durationMs": 60000,
            }
        ],
    )

    new_instances = {item.material_id.as_posix(): item for item in api.list_instances(project_id)}
    new_leaf_ids = {
        node.relative_path.as_posix(): node.node_id
        for node in api.list_learning_object_nodes(project_id)
        if isinstance(node, LearningObjectLeaf)
    }
    assert third_result["created_instances_count"] == 1
    assert third_result["reused_instances_count"] == 0
    assert new_instances["/课程/第一章/导论.mp4"].presence == InstancePresence.PRESENT
    assert new_leaf_ids["导论.mp4"] == old_leaf_ids["导论.mp4"]

    source_binding = api.get_project_material_source_binding(project_id)
    assert source_binding.source_kind == MaterialSourceKind.BAIDU_NETDISK
    assert source_binding.source_root_label == "第一章"


def test_import_baidu_netdisk_updates_binding_when_existing_path_metadata_changes() -> None:
    api = SystemAPI(InMemorySystem())
    project_id = api.create_project(
        "Course",
        initial_source_kind=MaterialSourceKind.MANUAL,
        initial_project_type=ProjectType.COURSE,
    )
    auth_store = _CloudAccountStore()

    api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=auth_store,  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-old",
                "path": "/课程/导论.mp4",
                "name": "导论.mp4",
                "mimeType": "video/mp4",
                "durationMs": 60000,
            }
        ],
    )

    result = api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=auth_store,  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-new",
                "path": "/课程/导论.mp4",
                "name": "导论.mp4",
                "mimeType": "video/mp4",
                "durationMs": 90000,
            }
        ],
    )

    assert result["unchanged"] is False
    assert result["created_instances_count"] == 0
    assert result["reused_instances_count"] == 1
    assert result["replaced_learning_object_nodes_count"] == 0

    session = api.sys.begin_session(project_id, SessionMode.READ_ONLY)
    try:
        bindings = api.sys.instance_media_binding_repo.all(session)
    finally:
        api.sys.rollback(session)
    assert len(bindings) == 1
    assert bindings[0].remote_file_id == "video-new"
    assert bindings[0].duration_ms == 90000


def test_baidu_direct_playback_descriptor_returns_playlist_without_server_segments(monkeypatch) -> None:
    api = SystemAPI(InMemorySystem())
    project_id = api.create_project(
        "Course",
        initial_source_kind=MaterialSourceKind.MANUAL,
        initial_project_type=ProjectType.COURSE,
    )

    def fake_decrypt_secret_value(ciphertext: str) -> str:
        assert ciphertext == "ciphertext"
        return "access-token"

    def fake_fetch_direct_hls_playlist(access_token: str, *, remote_path: str):
        assert access_token == "access-token"
        assert remote_path == "/课程/第一章/导论.mp4"

        class _Playlist:
            text = (
                "#EXTM3U\n"
                "#EXTINF:6,\n"
                "https://pan.baidu.com/video/segment0.ts?access_token=access-token\n"
            )
            upstream_url = "https://pan.baidu.com/video/index.m3u8"

        return _Playlist()

    monkeypatch.setattr("backend.system.instance_media.decrypt_secret_value", fake_decrypt_secret_value)
    monkeypatch.setattr(api._baidu_netdisk_client, "fetch_direct_hls_playlist", fake_fetch_direct_hls_playlist)

    api.import_learning_objects_from_baidu_netdisk(
        project_id,
        auth_store=_CloudAccountStore(),  # type: ignore[arg-type]
        user_id="user_1",
        account_id="account_1",
        items=[
            {
                "fileId": "video-1",
                "path": "/课程/第一章/导论.mp4",
                "name": "导论.mp4",
                "mimeType": "video/mp4",
                "durationMs": 60000,
            }
        ],
    )
    instance = api.list_instances(project_id)[0]

    descriptor = api.get_instance_baidu_direct_playback_descriptor(
        project_id,
        instance.instance_id,
        auth_store=_CloudAccountStore(),  # type: ignore[arg-type]
    )

    assert descriptor["sourceKind"] == "BAIDU_NETDISK"
    assert descriptor["playbackKind"] == "HLS"
    assert descriptor["mimeType"] == "application/vnd.apple.mpegurl"
    assert descriptor["durationMs"] == 60000
    assert descriptor["upstreamUrl"] == "https://pan.baidu.com/video/index.m3u8"
    assert "/segments/" not in descriptor["playlistText"]
    assert "https://pan.baidu.com/video/segment0.ts?access_token=access-token" in descriptor["playlistText"]


def test_baidu_direct_playlist_keeps_signed_media_urls_without_access_token() -> None:
    client = BaiduNetdiskClient()
    playlist = client._rewrite_hls_playlist_for_direct_access(
        access_token="access-token",
        upstream_url="https://pan.baidu.com/rest/2.0/xpan/file?method=streaming",
        text=(
            "#EXTM3U\n"
            "#EXTINF:10,\n"
            "https://v2-ant.baidu.com/file/segment.ts?fsid=1&fid=2&sign=sig&xcode=code\n"
        ),
    )

    assert "access_token=" not in playlist
    assert "https://v2-ant.baidu.com/file/segment.ts?fsid=1&fid=2&sign=sig&xcode=code" in playlist


def test_baidu_direct_playlist_adds_access_token_to_unsigned_baidu_urls() -> None:
    client = BaiduNetdiskClient()
    playlist = client._rewrite_hls_playlist_for_direct_access(
        access_token="access-token",
        upstream_url="https://pan.baidu.com/video/index.m3u8",
        text="#EXTM3U\n#EXTINF:6,\nsegment0.ts\n",
    )

    assert "https://pan.baidu.com/video/segment0.ts?access_token=access-token" in playlist


def test_begin_baidu_netdisk_connect_rejects_existing_enabled_account(tmp_path) -> None:
    api = SystemAPI(InMemorySystem())
    api._baidu_netdisk_client.enabled = True
    api._baidu_netdisk_client.client_id = "client-id"
    api._baidu_netdisk_client.client_secret = "client-secret"
    api._baidu_netdisk_client.redirect_uri = "https://example.test/api/auth/baidu-netdisk/callback"
    auth_store = SQLiteAuthStore(tmp_path / "auth.sqlite3")
    user = auth_store.create_user("baidu-single@example.com", "password-123")
    auth_store.upsert_user_cloud_account(
        user_id=user.user_id,
        provider=BAIDU_NETDISK_PROVIDER,
        provider_user_id="baidu-user",
        display_name="百度账号",
        avatar_url=None,
        access_token_ciphertext="access-ciphertext",
        refresh_token_ciphertext="refresh-ciphertext",
        expires_at=None,
        scope="basic,netdisk",
        meta={},
    )

    with pytest.raises(PreconditionFailure, match="只能绑定一个百度网盘账号"):
        api.begin_baidu_netdisk_connect(auth_store=auth_store, user_id=user.user_id)  # type: ignore[arg-type]


def test_complete_baidu_netdisk_connect_rejects_existing_enabled_account_before_token_exchange(tmp_path, monkeypatch) -> None:
    api = SystemAPI(InMemorySystem())
    auth_store = SQLiteAuthStore(tmp_path / "auth.sqlite3")
    user = auth_store.create_user("baidu-complete-single@example.com", "password-123")
    auth_store.upsert_user_cloud_account(
        user_id=user.user_id,
        provider=BAIDU_NETDISK_PROVIDER,
        provider_user_id="baidu-user",
        display_name="百度账号",
        avatar_url=None,
        access_token_ciphertext="access-ciphertext",
        refresh_token_ciphertext="refresh-ciphertext",
        expires_at=None,
        scope="basic,netdisk",
        meta={},
    )
    state = api._new_cloud_oauth_state(user_id=user.user_id, provider=BAIDU_NETDISK_PROVIDER)

    def unexpected_exchange_code(code: str):
        raise AssertionError("token exchange should not run when a Baidu Netdisk account is already bound")

    monkeypatch.setattr(api._baidu_netdisk_client, "exchange_code", unexpected_exchange_code)

    with pytest.raises(PreconditionFailure, match="只能绑定一个百度网盘账号"):
        api.complete_baidu_netdisk_connect(
            auth_store=auth_store,  # type: ignore[arg-type]
            user_id=user.user_id,
            code="oauth-code",
            state=state,
        )


def test_auth_store_rejects_second_enabled_baidu_netdisk_account(tmp_path) -> None:
    auth_store = SQLiteAuthStore(tmp_path / "auth.sqlite3")
    user = auth_store.create_user("baidu-store-single@example.com", "password-123")
    auth_store.upsert_user_cloud_account(
        user_id=user.user_id,
        provider=BAIDU_NETDISK_PROVIDER,
        provider_user_id="baidu-user-a",
        display_name="百度账号 A",
        avatar_url=None,
        access_token_ciphertext="access-ciphertext-a",
        refresh_token_ciphertext="refresh-ciphertext-a",
        expires_at=None,
        scope="basic,netdisk",
        meta={},
    )

    with pytest.raises(PreconditionFailure, match="只能绑定一个百度网盘账号"):
        auth_store.upsert_user_cloud_account(
            user_id=user.user_id,
            provider=BAIDU_NETDISK_PROVIDER,
            provider_user_id="baidu-user-b",
            display_name="百度账号 B",
            avatar_url=None,
            access_token_ciphertext="access-ciphertext-b",
            refresh_token_ciphertext="refresh-ciphertext-b",
            expires_at=None,
            scope="basic,netdisk",
            meta={},
        )
