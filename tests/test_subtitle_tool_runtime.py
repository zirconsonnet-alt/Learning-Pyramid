from __future__ import annotations

from pathlib import Path

import pytest

import tools.subtitle_tool as subtitle_tool
from tools.subtitle_tool import (
    RuntimePaths,
    build_whisper_command,
    configure_qt_display_scaling,
    discover_runtime_paths,
    normalize_recognition_language,
    parse_cuda_device_count,
    recognition_language_code_from_label,
    recognition_language_label,
    runtime_supports_cuda,
)


def _write_runtime_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _make_runtime_dir(tmp_path: Path, *, with_cuda: bool) -> Path:
    root = tmp_path / "runtime"
    _write_runtime_file(root / "ffmpeg" / "ffmpeg.exe")
    _write_runtime_file(root / "whispercpp" / "whisper-cli.exe")
    _write_runtime_file(root / "models" / "ggml-base.bin")
    if with_cuda:
        _write_runtime_file(root / "whispercpp" / "ggml-cuda.dll")
    return root


def test_discover_runtime_paths_marks_cuda_runtime_when_backend_exists(tmp_path: Path) -> None:
    runtime_root = _make_runtime_dir(tmp_path, with_cuda=True)

    runtime = discover_runtime_paths(runtime_root)

    assert runtime.root == runtime_root.resolve()
    assert runtime.cuda_backend == (runtime_root / "whispercpp" / "ggml-cuda.dll").resolve()
    assert runtime_supports_cuda(runtime) is True


def test_discover_runtime_paths_keeps_cpu_only_runtime_without_cuda_backend(tmp_path: Path) -> None:
    runtime_root = _make_runtime_dir(tmp_path, with_cuda=False)

    runtime = discover_runtime_paths(runtime_root)

    assert runtime.cuda_backend is None
    assert runtime_supports_cuda(runtime) is False


def test_build_whisper_command_for_cpu_mode_disables_gpu() -> None:
    runtime = RuntimePaths(
        root=Path("C:/runtime"),
        ffmpeg=Path("C:/runtime/ffmpeg.exe"),
        whisper_cli=Path("C:/runtime/whisper-cli.exe"),
        model=Path("C:/runtime/ggml-base.bin"),
        cuda_backend=Path("C:/runtime/ggml-cuda.dll"),
    )

    command = build_whisper_command(
        runtime=runtime,
        audio_path=Path("C:/tmp/input.wav"),
        output_prefix=Path("C:/tmp/out"),
        threads=6,
        enable_gpu=False,
        language="zh",
    )

    assert "-ng" in command
    assert command[:2] == [str(runtime.whisper_cli), "-m"]
    assert command[command.index("-l") + 1] == "zh"


def test_build_whisper_command_rejects_gpu_mode_without_cuda_backend() -> None:
    runtime = RuntimePaths(
        root=Path("C:/runtime"),
        ffmpeg=Path("C:/runtime/ffmpeg.exe"),
        whisper_cli=Path("C:/runtime/whisper-cli.exe"),
        model=Path("C:/runtime/ggml-base.bin"),
    )

    with pytest.raises(RuntimeError, match="CUDA backend"):
        build_whisper_command(
            runtime=runtime,
            audio_path=Path("C:/tmp/input.wav"),
            output_prefix=Path("C:/tmp/out"),
            threads=4,
            enable_gpu=True,
            language="zh",
        )


def test_build_whisper_command_allows_gpu_mode_when_cuda_backend_is_present() -> None:
    runtime = RuntimePaths(
        root=Path("C:/runtime"),
        ffmpeg=Path("C:/runtime/ffmpeg.exe"),
        whisper_cli=Path("C:/runtime/whisper-cli.exe"),
        model=Path("C:/runtime/ggml-base.bin"),
        cuda_backend=Path("C:/runtime/ggml-cuda.dll"),
    )

    command = build_whisper_command(
        runtime=runtime,
        audio_path=Path("C:/tmp/input.wav"),
        output_prefix=Path("C:/tmp/out"),
        threads=4,
        enable_gpu=True,
        language="auto",
    )

    assert "-ng" not in command
    assert command[-2:] == ["-of", str(Path("C:/tmp/out"))]
    assert command[command.index("-l") + 1] == "auto"


def test_parse_cuda_device_count_handles_whisper_cpp_cuda_output() -> None:
    assert parse_cuda_device_count("ggml_cuda_init: found 1 CUDA devices (Total VRAM: 6143 MiB)") == 1
    assert parse_cuda_device_count("ggml_cuda_init: found 0 CUDA devices") == 0
    assert parse_cuda_device_count("usage: whisper-cli.exe -h") is None


def test_recognition_language_helpers_default_to_chinese() -> None:
    assert normalize_recognition_language(None) == "zh"
    assert normalize_recognition_language("  xx  ") == "zh"
    assert recognition_language_label("zh") == "中文（推荐）"
    assert recognition_language_code_from_label("自动检测") == "auto"


def test_configure_qt_display_scaling_prefers_rounded_scale_factors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class FakeQGuiApplication:
        @staticmethod
        def setHighDpiScaleFactorRoundingPolicy(value: object) -> None:
            calls.append(value)

    class FakeQt:
        class HighDpiScaleFactorRoundingPolicy:
            Round = "round"

    monkeypatch.setattr(subtitle_tool, "PYSIDE6_AVAILABLE", True)
    monkeypatch.setattr(subtitle_tool, "QGuiApplication", FakeQGuiApplication, raising=False)
    monkeypatch.setattr(subtitle_tool, "Qt", FakeQt, raising=False)

    configure_qt_display_scaling()

    assert calls == ["round"]


def test_configure_qt_display_scaling_skips_when_rounding_policy_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class FakeQGuiApplication:
        @staticmethod
        def setHighDpiScaleFactorRoundingPolicy(value: object) -> None:
            calls.append(value)

    class FakeQt:
        pass

    monkeypatch.setattr(subtitle_tool, "PYSIDE6_AVAILABLE", True)
    monkeypatch.setattr(subtitle_tool, "QGuiApplication", FakeQGuiApplication, raising=False)
    monkeypatch.setattr(subtitle_tool, "Qt", FakeQt, raising=False)

    configure_qt_display_scaling()

    assert calls == []
