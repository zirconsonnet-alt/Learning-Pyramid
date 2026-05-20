import threading
import json
from pathlib import Path

import pytest

from tools import subtitle_tool


def test_learningpyramid_api_base_url_accepts_site_root_and_api_root() -> None:
    assert subtitle_tool.normalize_learningpyramid_api_base_url("https://plm.xuebao.chat") == "https://plm.xuebao.chat/api"
    assert subtitle_tool.normalize_learningpyramid_api_base_url("https://plm.xuebao.chat/api/") == "https://plm.xuebao.chat/api"


def test_parser_accepts_mobile_package_options() -> None:
    args = subtitle_tool.build_parser().parse_args(
        [
            "--mobile-package-dir",
            "C:/course",
            "--mobile-package-title",
            "移动课程",
            "--mobile-subject-id",
            "subj_1",
            "--mobile-project-id",
            "proj_1",
        ]
    )

    assert args.mobile_package_dir == "C:/course"
    assert args.mobile_package_title == "移动课程"
    assert args.mobile_subject_id == "subj_1"
    assert args.mobile_project_id == "proj_1"


def test_build_mobile_package_session_from_args_materializes_package_root(tmp_path) -> None:
    input_dir = tmp_path / "course-a"
    input_dir.mkdir()
    (input_dir / "01.mp4").write_bytes(b"video")
    (input_dir / "01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n字幕\n", encoding="utf-8")

    args = subtitle_tool.build_parser().parse_args(
        [
            "--mobile-package-dir",
            str(input_dir),
            "--mobile-package-title",
            "手机课程",
            "--mobile-subject-id",
            "subj_1",
            "--mobile-project-id",
            "proj_1",
        ]
    )

    session = subtitle_tool.build_mobile_package_session_from_args(args)
    package_root = input_dir.parent / f"{input_dir.name}.learningpyramid-mobile-package"

    assert session.root == package_root
    assert session.manifest["title"] == "手机课程"
    assert session.manifest["subjectId"] == "subj_1"
    assert session.manifest["scopedProjectId"] == "proj_1"
    assert (package_root / "manifest.json").is_file()
    assert (package_root / "videos" / "01.mp4").is_file()

    manifest_on_disk = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_on_disk == session.manifest


def test_run_cli_mobile_package_mode_skips_runtime_discovery(monkeypatch, tmp_path) -> None:
    input_dir = tmp_path / "course-a"
    input_dir.mkdir()
    captured_sessions: list[object] = []
    captured_servers: list[object] = []

    class FakeServer:
        base_url = "http://127.0.0.1:12345"

        def stop(self) -> None:
            captured_servers.append("stopped")

    def fail_discover_runtime_paths(runtime_dir=None):
        raise AssertionError("mobile package mode must not discover subtitle runtime paths")

    def fake_build_session(args):
        captured_sessions.append(args)
        return subtitle_tool.OfflineCoursePackageSession(
            root=input_dir,
            manifest={
                "manifestVersion": 1,
                "packageId": "pkg_1",
                "title": "手机课程",
                "createdAt": "2026-05-20T00:00:00+00:00",
                "subjectId": "subj_1",
                "scopedProjectId": "proj_1",
                "source": {"tool": "LearningPyramid-SubtitleTool", "version": "local"},
                "items": [{"video": {"path": "videos/01.mp4", "sizeBytes": 0, "sha256": "0" * 64}}],
            },
            token="token_1",
            expires_at_epoch=1.0,
        )

    monkeypatch.setattr(subtitle_tool, "discover_runtime_paths", fail_discover_runtime_paths)
    monkeypatch.setattr(subtitle_tool, "build_mobile_package_session_from_args", fake_build_session)
    monkeypatch.setattr(subtitle_tool, "start_offline_course_package_server", lambda session: FakeServer())
    monkeypatch.setattr(subtitle_tool, "_wait_for_mobile_package_server_interrupt", lambda: None)

    args = subtitle_tool.build_parser().parse_args(
        [
            "--mobile-package-dir",
            str(input_dir),
            "--mobile-package-title",
            "手机课程",
            "--mobile-subject-id",
            "subj_1",
            "--mobile-project-id",
            "proj_1",
        ]
    )

    assert subtitle_tool.run_cli(args) == 0
    assert captured_sessions == [args]
    assert captured_servers == ["stopped"]


def test_main_runs_mobile_package_cli_without_input_dir(monkeypatch) -> None:
    captured: list[object] = []

    def fake_run_cli(args):
        captured.append(args)
        return 0

    monkeypatch.setattr(subtitle_tool, "run_cli", fake_run_cli)

    assert (
        subtitle_tool.main(
            [
                "--mobile-package-dir",
                "C:/course",
                "--mobile-subject-id",
                "subj_1",
                "--mobile-project-id",
                "proj_1",
            ]
        )
        == 0
    )
    assert len(captured) == 1


class _ProjectClient:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str]] = []
        self.imports: list[tuple[str, str, str, list[dict[str, object]]]] = []

    def list_instances(self, subject_id: str, scoped_project_id: str):
        assert subject_id == "subj_1"
        assert scoped_project_id == "proj_1"
        return [
            {
                "instanceId": "inst_baidu",
                "materialDisplayName": "导论.mp4",
                "mediaSourceKind": "BAIDU_NETDISK",
                "playbackKind": "HLS",
            },
            {
                "instanceId": "inst_local",
                "materialDisplayName": "本地.mp4",
                "mediaSourceKind": "NATIVE_LOCAL",
                "playbackKind": "FILE",
            },
        ]

    def list_baidu_netdisk_accounts(self):
        return [{"accountId": "acct_1", "displayName": "百度账号"}]

    def list_project_baidu_netdisk_files(self, subject_id: str, scoped_project_id: str, account_id: str, *, dir_path: str, page: int = 1):
        assert subject_id == "subj_1"
        assert scoped_project_id == "proj_1"
        assert account_id == "acct_1"
        assert page == 1
        if dir_path == "/课程":
            return {
                "items": [
                    {
                        "fileId": "dir_1",
                        "path": "/课程/第一章",
                        "name": "第一章",
                        "isDir": True,
                    }
                ],
                "hasMore": False,
            }
        return {"items": [], "hasMore": False}

    def import_learning_objects_from_baidu_netdisk(self, subject_id: str, scoped_project_id: str, account_id: str, *, items):
        self.imports.append((subject_id, scoped_project_id, account_id, list(items)))
        return {"imported_count": len(items)}

    def get_instance_subtitle_file(self, subject_id: str, scoped_project_id: str, instance_id: str):
        assert subject_id == "subj_1"
        assert scoped_project_id == "proj_1"
        assert instance_id == "inst_baidu"
        return {"found": False, "instanceId": instance_id}

    def get_instance_baidu_direct_playback_descriptor(self, subject_id: str, scoped_project_id: str, instance_id: str):
        assert subject_id == "subj_1"
        assert scoped_project_id == "proj_1"
        assert instance_id == "inst_baidu"
        return {
            "instanceId": instance_id,
            "sourceKind": "BAIDU_NETDISK",
            "playbackKind": "HLS",
            "playlistText": "#EXTM3U\n#EXTINF:5,\nhttps://pan.baidu.com/video/segment0.ts\n",
            "upstreamUrl": "https://pan.baidu.com/video/index.m3u8",
            "mimeType": "application/vnd.apple.mpegurl",
            "durationMs": 5000,
        }

    def upload_instance_subtitle_file(self, subject_id: str, scoped_project_id: str, instance_id: str, *, file_name: str, content: str):
        assert subject_id == "subj_1"
        assert scoped_project_id == "proj_1"
        self.uploads.append((instance_id, file_name, content))
        return {"found": True, "instanceId": instance_id, "fileName": file_name, "format": "srt", "segments": []}


def test_project_baidu_batch_scans_project_instances_and_uploads_generated_subtitles(monkeypatch, tmp_path) -> None:
    client = _ProjectClient()
    runtime = subtitle_tool.RuntimePaths(
        root=tmp_path,
        ffmpeg=tmp_path / "ffmpeg.exe",
        whisper_cli=tmp_path / "whisper-cli.exe",
        model=tmp_path / "ggml-base.bin",
    )

    def fake_generate_subtitle_for_baidu_hls(**kwargs):
        assert kwargs["display_name"] == "导论.mp4"
        assert "#EXTM3U" in kwargs["playlist_text"]
        return "1\n00:00:00,000 --> 00:00:01,000\n网盘字幕\n"

    monkeypatch.setattr(subtitle_tool, "generate_subtitle_for_baidu_hls", fake_generate_subtitle_for_baidu_hls)

    summary = subtitle_tool.run_project_baidu_batch(
        subtitle_tool.ProjectBaiduBatchOptions(
            api_base_url="https://plm.xuebao.chat/api",
            email="user@example.com",
            password="password-123",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            overwrite=False,
            threads=2,
            enable_gpu=False,
            language="zh",
        ),
        runtime,
        client=client,
        log=lambda _text: None,
        progress=lambda _done, _total, _video, _detail: None,
        cancel_event=threading.Event(),
        process_controller=subtitle_tool.ProcessController(),
    )

    assert summary.total == 1
    assert summary.generated == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert client.uploads == [("inst_baidu", "导论.srt", "1\n00:00:00,000 --> 00:00:01,000\n网盘字幕\n")]


def test_generate_subtitle_for_baidu_hls_uses_temp_playlist_and_returns_generated_srt(monkeypatch, tmp_path) -> None:
    runtime = subtitle_tool.RuntimePaths(
        root=tmp_path,
        ffmpeg=tmp_path / "ffmpeg.exe",
        whisper_cli=tmp_path / "whisper-cli.exe",
        model=tmp_path / "ggml-base.bin",
    )
    commands: list[list[str]] = []
    playlist_snapshots: list[str] = []

    def fake_run_process(command, *, cancel_event, process_controller, on_heartbeat=None):
        commands.append(command)
        if command[0] == str(runtime.ffmpeg):
            playlist_path = Path(command[command.index("-i") + 1])
            playlist_snapshots.append(playlist_path.read_text(encoding="utf-8"))
            return
        if command[0] == str(runtime.whisper_cli):
            output_prefix = Path(command[command.index("-of") + 1])
            subtitle_tool.whisper_output_file(output_prefix, ".srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n生成字幕\n",
                encoding="utf-8",
            )
            return
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subtitle_tool, "_run_process", fake_run_process)

    result = subtitle_tool.generate_subtitle_for_baidu_hls(
        display_name="导论.mp4",
        playlist_text="#EXTM3U\n#EXTINF:5,\nhttps://pan.baidu.com/video/segment0.ts\n",
        runtime=runtime,
        threads=2,
        enable_gpu=False,
        language="zh",
        cancel_event=threading.Event(),
        process_controller=subtitle_tool.ProcessController(),
        log=lambda _text: None,
        progress=lambda _stage_progress, _detail: None,
    )

    assert playlist_snapshots == ["#EXTM3U\n#EXTINF:5,\nhttps://pan.baidu.com/video/segment0.ts\n"]
    assert commands[0][0] == str(runtime.ffmpeg)
    assert commands[1][0] == str(runtime.whisper_cli)
    assert result == "1\n00:00:00,000 --> 00:00:01,000\n生成字幕\n"


def test_run_cli_uses_project_baidu_mode_without_local_input_dir(monkeypatch, tmp_path) -> None:
    runtime = subtitle_tool.RuntimePaths(
        root=tmp_path,
        ffmpeg=tmp_path / "ffmpeg.exe",
        whisper_cli=tmp_path / "whisper-cli.exe",
        model=tmp_path / "ggml-base.bin",
    )
    captured: list[subtitle_tool.ProjectBaiduBatchOptions] = []

    monkeypatch.setattr(subtitle_tool, "discover_runtime_paths", lambda runtime_dir=None: runtime)

    def fake_run_project_baidu_batch(options, runtime_arg, **kwargs):
        assert runtime_arg is runtime
        captured.append(options)
        return subtitle_tool.BatchSummary(total=1, generated=1)

    monkeypatch.setattr(subtitle_tool, "run_project_baidu_batch", fake_run_project_baidu_batch)

    args = subtitle_tool.build_parser().parse_args(
        [
            "--lp-api-base-url",
            "https://plm.xuebao.chat",
            "--lp-email",
            "user@example.com",
            "--lp-password",
            "password-123",
            "--lp-subject-id",
            "subj_1",
            "--lp-project-id",
            "proj_1",
            "--threads",
            "3",
            "--overwrite",
        ]
    )

    assert subtitle_tool.run_cli(args) == 0
    assert captured == [
        subtitle_tool.ProjectBaiduBatchOptions(
            api_base_url="https://plm.xuebao.chat/api",
            email="user@example.com",
            password="password-123",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            overwrite=True,
            threads=3,
            enable_gpu=False,
            language="zh",
            baidu_account_id=None,
            baidu_import_paths=(),
        )
    ]


def test_run_cli_passes_project_baidu_import_options(monkeypatch, tmp_path) -> None:
    runtime = subtitle_tool.RuntimePaths(
        root=tmp_path,
        ffmpeg=tmp_path / "ffmpeg.exe",
        whisper_cli=tmp_path / "whisper-cli.exe",
        model=tmp_path / "ggml-base.bin",
    )
    captured: list[subtitle_tool.ProjectBaiduBatchOptions] = []

    monkeypatch.setattr(subtitle_tool, "discover_runtime_paths", lambda runtime_dir=None: runtime)

    def fake_run_project_baidu_batch(options, runtime_arg, **kwargs):
        assert runtime_arg is runtime
        captured.append(options)
        return subtitle_tool.BatchSummary(total=1, generated=1)

    monkeypatch.setattr(subtitle_tool, "run_project_baidu_batch", fake_run_project_baidu_batch)

    args = subtitle_tool.build_parser().parse_args(
        [
            "--lp-api-base-url",
            "https://plm.xuebao.chat",
            "--lp-email",
            "user@example.com",
            "--lp-password",
            "password-123",
            "--lp-subject-id",
            "subj_1",
            "--lp-project-id",
            "proj_1",
            "--lp-baidu-account-id",
            "acct_1",
            "--lp-baidu-import-path",
            "/课程/第一章",
            "--lp-baidu-import-path",
            "/课程/第二章",
        ]
    )

    assert subtitle_tool.run_cli(args) == 0
    assert captured == [
        subtitle_tool.ProjectBaiduBatchOptions(
            api_base_url="https://plm.xuebao.chat/api",
            email="user@example.com",
            password="password-123",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            overwrite=False,
            threads=subtitle_tool.default_threads(),
            enable_gpu=False,
            language="zh",
            baidu_account_id="acct_1",
            baidu_import_paths=("/课程/第一章", "/课程/第二章"),
        )
    ]


def test_main_runs_project_baidu_cli_without_input_dir(monkeypatch) -> None:
    captured: list[object] = []

    def fake_run_cli(args):
        captured.append(args)
        return 0

    class FakeApp:
        def __init__(self, runtime_dir=None) -> None:
            self.runtime_dir = runtime_dir

        def run(self) -> int:
            return 99

    monkeypatch.setattr(subtitle_tool, "run_cli", fake_run_cli)
    monkeypatch.setattr(subtitle_tool, "PYSIDE6_AVAILABLE", False)
    monkeypatch.setattr(subtitle_tool, "SubtitleToolApp", FakeApp)

    assert (
        subtitle_tool.main(
            [
                "--lp-api-base-url",
                "https://plm.xuebao.chat",
                "--lp-email",
                "user@example.com",
                "--lp-password",
                "password-123",
                "--lp-subject-id",
                "subj_1",
                "--lp-project-id",
                "proj_1",
                "--lp-baidu-import-path",
                "/课程/第一章",
            ]
        )
        == 0
    )
    assert len(captured) == 1


def test_project_baidu_batch_imports_selected_netdisk_path_before_generating(monkeypatch, tmp_path) -> None:
    client = _ProjectClient()
    runtime = subtitle_tool.RuntimePaths(
        root=tmp_path,
        ffmpeg=tmp_path / "ffmpeg.exe",
        whisper_cli=tmp_path / "whisper-cli.exe",
        model=tmp_path / "ggml-base.bin",
    )

    monkeypatch.setattr(
        subtitle_tool,
        "generate_subtitle_for_baidu_hls",
        lambda **_kwargs: "1\n00:00:00,000 --> 00:00:01,000\n网盘字幕\n",
    )

    summary = subtitle_tool.run_project_baidu_batch(
        subtitle_tool.ProjectBaiduBatchOptions(
            api_base_url="https://plm.xuebao.chat/api",
            email="user@example.com",
            password="password-123",
            subject_id="subj_1",
            scoped_project_id="proj_1",
            overwrite=False,
            threads=2,
            enable_gpu=False,
            language="zh",
            baidu_account_id=None,
            baidu_import_paths=("/课程/第一章",),
        ),
        runtime,
        client=client,
        log=lambda _text: None,
        progress=lambda _done, _total, _video, _detail: None,
        cancel_event=threading.Event(),
        process_controller=subtitle_tool.ProcessController(),
    )

    assert summary.generated == 1
    assert client.imports == [
        (
            "subj_1",
            "proj_1",
            "acct_1",
            [
                {
                    "fileId": "dir_1",
                    "path": "/课程/第一章",
                    "name": "第一章",
                    "isDir": True,
                }
            ],
        )
    ]
    assert client.uploads[0][0] == "inst_baidu"
