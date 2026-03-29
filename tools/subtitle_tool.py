from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk


APP_TITLE = "LearningPyramid 字幕生成工具"
DEFAULT_MODEL_FILE = "ggml-base.bin"
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".wmv", ".flv")


class CancelledError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    ffmpeg: Path
    whisper_cli: Path
    model: Path


@dataclass(frozen=True)
class BatchOptions:
    input_dir: Path
    recursive: bool
    overwrite: bool
    threads: int


@dataclass
class BatchSummary:
    total: int
    generated: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


class ProcessController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def attach(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._process = process

    def clear(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._process is process:
                self._process = None

    def terminate(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
        except Exception:
            return


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_threads() -> int:
    cpu_count = os.cpu_count() or 4
    return max(1, min(cpu_count, 8))


def discover_runtime_paths(runtime_dir: Path | None = None) -> RuntimePaths:
    candidates: list[Path] = []
    configured_runtime = (os.getenv("LP_SUBTITLE_TOOL_RUNTIME_DIR") or "").strip()
    if runtime_dir is not None:
        candidates.append(runtime_dir.expanduser().resolve())
    if configured_runtime:
        candidates.append(Path(configured_runtime).expanduser().resolve())

    base_dir = executable_dir()
    script_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            (base_dir / "runtime").resolve(),
            (base_dir / "subtitle-tool-runtime").resolve(),
            (script_dir / "runtime").resolve(),
            (script_dir.parent / "build" / "subtitle-tool" / "runtime").resolve(),
        ]
    )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        runtime = _try_make_runtime_paths(candidate)
        if runtime is not None:
            return runtime

    raise FileNotFoundError(
        "未找到内置运行时目录。请确认工具包中的 runtime 目录、ffmpeg.exe、whisper-cli.exe 和 ggml-base.bin 都在。"
    )


def _try_make_runtime_paths(root: Path) -> RuntimePaths | None:
    if not root.exists() or not root.is_dir():
        return None

    ffmpeg = _find_first_file(root, ("ffmpeg.exe", "ffmpeg"))
    whisper_cli = _find_first_file(root, ("whisper-cli.exe", "whisper-cli"))
    model = _find_first_file(root, (DEFAULT_MODEL_FILE,))
    if ffmpeg is None or whisper_cli is None or model is None:
        return None
    return RuntimePaths(root=root, ffmpeg=ffmpeg, whisper_cli=whisper_cli, model=model)


def _find_first_file(root: Path, names: tuple[str, ...]) -> Path | None:
    wanted = {name.lower() for name in names}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name.lower() in wanted:
            return path
    return None


def iter_video_files(root: Path, recursive: bool) -> list[Path]:
    iterator = root.rglob("*") if recursive else root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def run_batch(
    options: BatchOptions,
    runtime: RuntimePaths,
    *,
    log: callable,
    progress: callable,
    cancel_event: threading.Event,
    process_controller: ProcessController,
) -> BatchSummary:
    if not options.input_dir.exists() or not options.input_dir.is_dir():
        raise FileNotFoundError(f"目录不存在：{options.input_dir}")

    videos = iter_video_files(options.input_dir, recursive=options.recursive)
    if not videos:
        raise FileNotFoundError("当前目录下没有找到支持的视频文件。")

    summary = BatchSummary(total=len(videos))
    for index, video_path in enumerate(videos, start=1):
        if cancel_event.is_set():
            raise CancelledError("任务已取消。")

        subtitle_path = video_path.with_suffix(".srt")
        progress(index - 1, summary.total, video_path)

        if subtitle_path.exists() and not options.overwrite:
            summary.skipped += 1
            log(f"[{index}/{summary.total}] 跳过 {video_path.name}，同名字幕已存在。")
            progress(index, summary.total, video_path)
            continue

        try:
            log(f"[{index}/{summary.total}] 正在处理 {video_path.name}")
            generate_subtitle_for_video(
                video_path=video_path,
                subtitle_path=subtitle_path,
                runtime=runtime,
                threads=options.threads,
                cancel_event=cancel_event,
                process_controller=process_controller,
            )
            summary.generated += 1
            log(f"[{index}/{summary.total}] 已生成 {subtitle_path.name}")
        except CancelledError:
            raise
        except Exception as exc:
            summary.failed += 1
            error_text = f"{video_path.name}: {exc}"
            summary.failures.append(error_text)
            log(f"[{index}/{summary.total}] 失败 {error_text}")

        progress(index, summary.total, video_path)

    return summary


def generate_subtitle_for_video(
    *,
    video_path: Path,
    subtitle_path: Path,
    runtime: RuntimePaths,
    threads: int,
    cancel_event: threading.Event,
    process_controller: ProcessController,
) -> None:
    with tempfile.TemporaryDirectory(prefix="lp-subtitle-tool-") as tmpdir:
        tmp_root = Path(tmpdir)
        wav_path = tmp_root / f"{video_path.stem}.wav"
        output_prefix = tmp_root / video_path.stem

        _run_process(
            [
                str(runtime.ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            cancel_event=cancel_event,
            process_controller=process_controller,
        )

        _run_process(
            [
                str(runtime.whisper_cli),
                "-m",
                str(runtime.model),
                "-f",
                str(wav_path),
                "-t",
                str(max(1, threads)),
                "-osrt",
                "-of",
                str(output_prefix),
            ],
            cancel_event=cancel_event,
            process_controller=process_controller,
        )

        generated_srt = output_prefix.with_suffix(".srt")
        if not generated_srt.exists():
            raise RuntimeError("whisper.cpp 没有产出 .srt 文件。")
        subtitle_path.write_bytes(generated_srt.read_bytes())


def _run_process(
    command: list[str],
    *,
    cancel_event: threading.Event,
    process_controller: ProcessController,
) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    process_controller.attach(process)
    try:
        while True:
            if cancel_event.is_set():
                process_controller.terminate()
                raise CancelledError("任务已取消。")
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        process_controller.clear(process)

    if process.returncode != 0:
        detail = (stderr or stdout or "子进程执行失败").strip()
        raise RuntimeError(detail[:600])


def print_runtime_summary(runtime: RuntimePaths) -> str:
    return f"ffmpeg={runtime.ffmpeg.name} | whisper={runtime.whisper_cli.name} | model={runtime.model.name}"


class SubtitleToolApp:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = runtime_dir
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("880x680")
        self.root.minsize(760, 560)

        self.input_dir_var = tk.StringVar()
        self.runtime_var = tk.StringVar(value="正在检查内置运行时...")
        self.status_var = tk.StringVar(value="请选择一个视频目录。")
        self.progress_label_var = tk.StringVar(value="尚未开始")
        self.recursive_var = tk.BooleanVar(value=True)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.threads_var = tk.IntVar(value=default_threads())
        self.progress_value_var = tk.DoubleVar(value=0.0)

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.process_controller = ProcessController()
        self.worker_thread: threading.Thread | None = None

        self._build_ui()
        self._refresh_runtime_summary()
        self.root.after(120, self._poll_events)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        shell = ttk.Frame(self.root, padding=18)
        shell.grid(sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(4, weight=1)

        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="离线批量扫描视频目录，生成同目录同名 .srt 字幕文件。",
            foreground="#4b5563",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        runtime_frame = ttk.LabelFrame(shell, text="内置组件", padding=14)
        runtime_frame.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        runtime_frame.columnconfigure(0, weight=1)
        ttk.Label(runtime_frame, textvariable=self.runtime_var, wraplength=760).grid(row=0, column=0, sticky="w")

        config_frame = ttk.LabelFrame(shell, text="处理设置", padding=14)
        config_frame.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(3, weight=1)

        ttk.Label(config_frame, text="视频目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.input_dir_var).grid(row=0, column=1, sticky="ew", padx=(10, 10))
        ttk.Button(config_frame, text="选择目录", command=self._choose_directory).grid(row=0, column=2, sticky="ew")

        ttk.Checkbutton(config_frame, text="递归处理子目录", variable=self.recursive_var).grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Checkbutton(config_frame, text="覆盖已有 .srt", variable=self.overwrite_var).grid(row=1, column=1, sticky="w", pady=(12, 0))
        ttk.Label(config_frame, text="线程数").grid(row=1, column=2, sticky="e", padx=(10, 6), pady=(12, 0))
        ttk.Spinbox(config_frame, from_=1, to=16, textvariable=self.threads_var, width=8).grid(row=1, column=3, sticky="w", pady=(12, 0))

        progress_frame = ttk.LabelFrame(shell, text="当前进度", padding=14)
        progress_frame.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        progress_frame.columnconfigure(0, weight=1)
        ttk.Label(progress_frame, textvariable=self.progress_label_var).grid(row=0, column=0, sticky="w")
        ttk.Progressbar(progress_frame, variable=self.progress_value_var, maximum=100).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(progress_frame, textvariable=self.status_var, foreground="#4b5563", wraplength=760).grid(row=2, column=0, sticky="w", pady=(10, 0))

        log_frame = ttk.LabelFrame(shell, text="处理日志", padding=14)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(16, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", height=18, state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(shell)
        actions.grid(row=5, column=0, sticky="e", pady=(16, 0))
        self.start_button = ttk.Button(actions, text="开始生成", command=self._start)
        self.start_button.grid(row=0, column=0)
        self.cancel_button = ttk.Button(actions, text="取消", command=self._cancel, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(10, 0))

    def _choose_directory(self) -> None:
        initial_dir = self.input_dir_var.get().strip() or str(executable_dir())
        selected = filedialog.askdirectory(initialdir=initial_dir, title="选择要生成字幕的视频目录")
        if selected:
            self.input_dir_var.set(selected)

    def _refresh_runtime_summary(self) -> None:
        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            self.runtime_var.set(f"未检测到内置运行时：{exc}")
            return
        self.runtime_var.set(print_runtime_summary(runtime))

    def _start(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return

        input_dir_text = self.input_dir_var.get().strip()
        if not input_dir_text:
            messagebox.showerror(APP_TITLE, "请先选择一个视频目录。")
            return

        input_dir = Path(input_dir_text).expanduser()
        try:
            runtime = discover_runtime_paths(self.runtime_dir)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        options = BatchOptions(
            input_dir=input_dir,
            recursive=bool(self.recursive_var.get()),
            overwrite=bool(self.overwrite_var.get()),
            threads=max(1, int(self.threads_var.get() or 1)),
        )
        self._append_log("")
        self._append_log(f"开始任务：{options.input_dir}")
        self._append_log(print_runtime_summary(runtime))

        self.cancel_event.clear()
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress_value_var.set(0.0)
        self.progress_label_var.set("准备扫描目录...")
        self.status_var.set("正在扫描视频文件并准备逐个生成字幕。")

        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(options, runtime),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_worker(self, options: BatchOptions, runtime: RuntimePaths) -> None:
        try:
            summary = run_batch(
                options,
                runtime,
                log=lambda text: self.event_queue.put(("log", text)),
                progress=lambda done, total, video: self.event_queue.put(("progress", (done, total, str(video)))),
                cancel_event=self.cancel_event,
                process_controller=self.process_controller,
            )
            self.event_queue.put(("done", summary))
        except CancelledError as exc:
            self.event_queue.put(("cancelled", str(exc)))
        except Exception as exc:
            self.event_queue.put(("error", str(exc)))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.process_controller.terminate()
        self.status_var.set("正在尝试取消当前任务...")

    def _poll_events(self) -> None:
        while True:
            try:
                event_name, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == "log":
                self._append_log(str(payload))
                continue

            if event_name == "progress":
                done, total, current = payload
                total_count = max(1, int(total))
                self.progress_value_var.set(max(0.0, min(100.0, float(done) / float(total_count) * 100.0)))
                self.progress_label_var.set(f"{done}/{total_count} · {Path(str(current)).name}")
                continue

            if event_name == "done":
                summary = payload
                assert isinstance(summary, BatchSummary)
                self._finish_work()
                self.status_var.set(
                    f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。"
                )
                if summary.failures:
                    self._append_log("失败详情：")
                    for item in summary.failures:
                        self._append_log(item)
                messagebox.showinfo(
                    APP_TITLE,
                    f"处理完成。\n生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。",
                )
                continue

            if event_name == "cancelled":
                self._finish_work()
                self.status_var.set(str(payload))
                self._append_log(str(payload))
                continue

            if event_name == "error":
                self._finish_work()
                self.status_var.set(str(payload))
                self._append_log(str(payload))
                messagebox.showerror(APP_TITLE, str(payload))

        self.root.after(120, self._poll_events)

    def _finish_work(self) -> None:
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_cli(args: argparse.Namespace) -> int:
    runtime = discover_runtime_paths(Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else None)
    options = BatchOptions(
        input_dir=Path(args.input_dir).expanduser().resolve(),
        recursive=not bool(args.non_recursive),
        overwrite=bool(args.overwrite),
        threads=max(1, int(args.threads or 1)),
    )
    cancel_event = threading.Event()
    process_controller = ProcessController()
    summary = run_batch(
        options,
        runtime,
        log=lambda text: print(text),
        progress=lambda done, total, video: print(f"进度 {done}/{total}: {video}"),
        cancel_event=cancel_event,
        process_controller=process_controller,
    )
    print(f"完成：生成 {summary.generated} 个，跳过 {summary.skipped} 个，失败 {summary.failed} 个。")
    return 0 if summary.failed == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate same-directory SRT subtitles for a video folder.")
    parser.add_argument("--input-dir", help="Run in headless mode for the given video directory.")
    parser.add_argument("--runtime-dir", help="Optional runtime directory containing ffmpeg, whisper-cli and the model.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .srt files.")
    parser.add_argument("--non-recursive", action="store_true", help="Only process the selected directory, not subdirectories.")
    parser.add_argument("--threads", type=int, default=default_threads(), help="whisper.cpp worker thread count.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.input_dir:
        return run_cli(args)
    app = SubtitleToolApp(runtime_dir=Path(args.runtime_dir).expanduser().resolve() if args.runtime_dir else None)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
