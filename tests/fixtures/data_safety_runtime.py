from __future__ import annotations

from pathlib import Path


def create_protected_root(tmp_path: Path, name: str = "protected-data") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    (root / ".data-safety-probe").write_text("ok", encoding="utf-8")
    return root


def create_project_media(root: Path, *, project_id: str = "proj_000001", asset_id: str = "asset_000001") -> Path:
    media_dir = root / project_id / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    media_file = media_dir / f"{asset_id}.png"
    media_file.write_bytes(b"fake-png")
    return media_file
