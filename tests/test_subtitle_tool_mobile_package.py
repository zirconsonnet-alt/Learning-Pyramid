import json
from pathlib import Path

from tools import subtitle_tool


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
