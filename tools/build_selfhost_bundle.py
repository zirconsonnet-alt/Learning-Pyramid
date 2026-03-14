from __future__ import annotations

import argparse
import subprocess
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _project_version() -> str:
    namespace: dict[str, object] = {}
    version_file = PROJECT_ROOT / "backend" / "system" / "version.py"
    exec(version_file.read_text(encoding="utf-8"), namespace)
    return str(namespace["APP_VERSION"])


def _bundle_name(version: str) -> str:
    return f"LearningPyramid-{version}-selfhost-source"


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".history", "node_modules", "dist"),
    )


def _copy_frontend_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".history", "node_modules"),
    )


def _resolve_pnpm_command() -> list[str]:
    for candidate in ("pnpm.cmd", "pnpm"):
        path = shutil.which(candidate)
        if path:
            return [path]
    for candidate in ("corepack.cmd", "corepack"):
        path = shutil.which(candidate)
        if path:
            return [path, "pnpm"]
    raise SystemExit("Could not find pnpm. Install pnpm or ensure corepack is available before building the self-host bundle.")


def _build_frontend() -> None:
    subprocess.run([*_resolve_pnpm_command(), "build"], cwd=str(PROJECT_ROOT / "frontend"), check=True)


def _ensure_frontend_dist(*, build_frontend: bool) -> None:
    if build_frontend:
        print("Building frontend/dist locally...")
        _build_frontend()
    index_file = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if not index_file.exists():
        raise SystemExit("frontend/dist is missing. Run `pnpm build` in frontend/ or pass --build-frontend.")


def _write_notes(dst: Path) -> None:
    text = """Server deploy quick start:
1. Extract this bundle into a standalone directory on the server.
2. Copy .env.selfhost.example to .env and edit secrets / host settings.
3. Start PostgreSQL deployment:
   docker compose -f docker-compose.selfhost.yml -f docker-compose.selfhost.postgres.yml --env-file .env up -d --build
4. Optional HTTPS reverse proxy:
   docker compose -f docker-compose.selfhost.yml -f docker-compose.selfhost.postgres.yml -f docker-compose.selfhost.proxy.yml --env-file .env up -d --build
"""
    (dst / "DEPLOY_SELFHOST.txt").write_text(text, encoding="utf-8", newline="\n")


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    parser.add_argument("--build-frontend", action="store_true")
    args = parser.parse_args()

    _ensure_frontend_dist(build_frontend=bool(args.build_frontend))

    version = _project_version()
    bundle_name = _bundle_name(version)
    output_root = Path(args.output_dir).resolve()
    bundle_dir = output_root / bundle_name
    zip_path = output_root / f"{bundle_name}.zip"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    for rel_dir in ("adapter", "backend", "docs", "tools"):
        _copy_tree(PROJECT_ROOT / rel_dir, bundle_dir / rel_dir)
    _copy_frontend_tree(PROJECT_ROOT / "frontend", bundle_dir / "frontend")

    for rel_file in (
        ".dockerignore",
        ".env.selfhost.example",
        "Caddyfile.selfhost",
        "Dockerfile",
        "Dockerfile.selfhost",
        "README.md",
        "requirements.txt",
        "docker-compose.selfhost.yml",
        "docker-compose.selfhost.postgres.yml",
        "docker-compose.selfhost.proxy.yml",
    ):
        dst = bundle_dir / rel_file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / rel_file, dst)

    _write_notes(bundle_dir)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)

    print(f"Self-host bundle directory: {bundle_dir}")
    print(f"Self-host bundle zip: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
