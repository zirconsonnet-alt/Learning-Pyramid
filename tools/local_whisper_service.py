import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import torch
import whisper


DEFAULT_MODEL = (os.getenv("WHISPER_MODEL") or "small").strip() or "small"
DEFAULT_DEVICE = (os.getenv("WHISPER_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")).strip() or "cpu"
DEFAULT_LANGUAGE = (os.getenv("WHISPER_LANGUAGE") or "").strip() or None

MODEL_CACHE: dict[tuple[str, str], Any] = {}
MODEL_LOCK = threading.Lock()
TRANSCRIBE_LOCK = threading.Lock()


def _json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _load_model(model_name: str, device: str):
    key = (model_name, device)
    with MODEL_LOCK:
        cached = MODEL_CACHE.get(key)
        if cached is None:
            cached = whisper.load_model(model_name, device=device)
            MODEL_CACHE[key] = cached
        return cached


def _extract_audio_clip(*, ffmpeg_bin: str, source_path: Path, start_ms: int, duration_ms: int, out_path: Path) -> None:
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-t",
        f"{duration_ms / 1000:.3f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _transcribe(req: dict[str, object]) -> dict[str, object]:
    provider = str(req.get("provider") or "WHISPER").strip().upper()
    if provider != "WHISPER":
        raise ValueError(f"Unsupported provider: {provider}")

    source = req.get("source")
    window = req.get("window")
    if not isinstance(source, dict) or not isinstance(window, dict):
        raise ValueError("source/window must be objects")

    source_path = Path(str(source.get("filePath") or "")).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError("source.filePath does not exist or is not a file")

    center_ms = int(window.get("centerMs", 0))
    pre_ms = int(window.get("preMs", 0))
    post_ms = int(window.get("postMs", 0))
    duration_ms = pre_ms + post_ms
    model_name = str(req.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    language = str(req.get("language") or DEFAULT_LANGUAGE or "").strip() or None

    if duration_ms <= 0:
        return {"segments": [], "provider": "WHISPER", "model": model_name, "device": DEFAULT_DEVICE}

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH")

    start_ms = max(center_ms - pre_ms, 0)
    with tempfile.TemporaryDirectory(prefix="learningpyramid-whisper-") as tmpdir:
        audio_path = Path(tmpdir) / "clip.wav"
        _extract_audio_clip(
            ffmpeg_bin=ffmpeg_bin,
            source_path=source_path,
            start_ms=start_ms,
            duration_ms=duration_ms,
            out_path=audio_path,
        )
        model = _load_model(model_name, DEFAULT_DEVICE)
        with TRANSCRIBE_LOCK:
            result = model.transcribe(
                str(audio_path),
                task="transcribe",
                language=language,
                verbose=False,
                fp16=DEFAULT_DEVICE.startswith("cuda"),
                condition_on_previous_text=False,
            )

    segments: list[dict[str, object]] = []
    for item in result.get("segments") or []:
        rel_start_ms = int(round(float(item.get("start", 0.0)) * 1000))
        rel_end_ms = int(round(float(item.get("end", 0.0)) * 1000))
        segments.append(
            {
                "startMs": start_ms + max(rel_start_ms, 0),
                "endMs": start_ms + max(rel_end_ms, max(rel_start_ms, 0)),
                "text": str(item.get("text", "")).strip(),
                "confidence": None,
            }
        )

    return {"segments": segments, "provider": "WHISPER", "model": model_name, "device": DEFAULT_DEVICE}


class WhisperHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = _json_bytes(payload)
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "provider": "WHISPER",
                "defaultModel": DEFAULT_MODEL,
                "device": DEFAULT_DEVICE,
                "language": DEFAULT_LANGUAGE,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/asr/request":
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"detail": "Invalid Content-Length"})
            return

        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            result = _transcribe(payload)
            self._send_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "ffmpeg failed").strip()
            self._send_json(HTTPStatus.BAD_REQUEST, {"detail": f"Failed to extract audio clip: {detail[:400]}"})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"detail": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, int(args.port)), WhisperHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
