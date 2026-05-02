from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_image_upload_has_image_specific_payload_too_large_message_and_compression() -> None:
    http_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "http.ts").read_text(encoding="utf-8")
    media_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "mediaAssets.ts").read_text(encoding="utf-8")

    assert "payloadTooLargeMessage" in http_source
    assert "上传的图片过大" in media_source
    assert "prepareImageFileForUpload" in media_source
    assert "IMAGE_UPLOAD_TARGET_BYTES" in media_source
    assert "canvas.toBlob" in media_source


def test_audio_uploads_keep_audio_specific_payload_too_large_message() -> None:
    asr_source = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "asr.ts").read_text(encoding="utf-8")

    assert "AUDIO_PAYLOAD_TOO_LARGE_MESSAGE" in asr_source
    assert asr_source.count("payloadTooLargeMessage: AUDIO_PAYLOAD_TOO_LARGE_MESSAGE") >= 2
