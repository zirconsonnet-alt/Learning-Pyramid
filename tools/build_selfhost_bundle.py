import argparse
import json
import subprocess
import shutil
from pathlib import Path, PurePosixPath
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


def _copy_optional_tree(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return
    _copy_tree(src, dst)


def _normalize_public_download_asset_path(asset_path: str) -> Path | None:
    normalized = str(asset_path or "").strip().replace("\\", "/")
    if not normalized:
        return None

    pure_path = PurePosixPath(normalized)
    if pure_path.is_absolute():
        return None

    safe_parts: list[str] = []
    for part in pure_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            return None
        safe_parts.append(part)

    if not safe_parts:
        return None
    return Path(*safe_parts)


def _copy_public_downloads_for_bundle(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return

    catalog_path = src / "catalog.json"
    if not catalog_path.exists():
        _copy_tree(src, dst)
        print("public-downloads/catalog.json is missing; copied the entire public-downloads/ tree.")
        return

    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        _copy_tree(src, dst)
        print("public-downloads/catalog.json is invalid JSON; copied the entire public-downloads/ tree.")
        return

    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        _copy_tree(src, dst)
        print("public-downloads/catalog.json has no valid items list; copied the entire public-downloads/ tree.")
        return

    src_root = src.resolve()
    copied_assets = 0
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(catalog_path, dst / "catalog.json")

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        normalized_rel_path = _normalize_public_download_asset_path(
            str(raw_item.get("assetPath") or raw_item.get("fileName") or "")
        )
        if normalized_rel_path is None:
            continue

        source_asset = (src_root / normalized_rel_path).resolve()
        try:
            source_asset.relative_to(src_root)
        except Exception:
            continue
        if not source_asset.exists() or not source_asset.is_file():
            continue

        target_asset = dst / normalized_rel_path
        target_asset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_asset, target_asset)
        copied_assets += 1

    if copied_assets == 0:
        shutil.rmtree(dst)
        _copy_tree(src, dst)
        print("public-downloads/catalog.json did not reference any local files; copied the entire public-downloads/ tree.")
        return

    print(f"Included public-downloads catalog plus {copied_assets} referenced asset file(s) in the bundle.")


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


def _clean_frontend_build_outputs() -> None:
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    tmp_dir = PROJECT_ROOT / "frontend" / "node_modules" / ".tmp"
    for buildinfo_name in ("tsconfig.app.tsbuildinfo", "tsconfig.node.tsbuildinfo"):
        buildinfo_path = tmp_dir / buildinfo_name
        if buildinfo_path.exists():
            buildinfo_path.unlink()


def _build_frontend() -> None:
    _clean_frontend_build_outputs()
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
3. Optional: copy .env.selfhost.sync.example to .env.selfhost.sync locally and keep that real file out of git.
   Sync-Selfhost-Server.bat will merge .env.selfhost.sync into the server's app/.env automatically on deploy.
4. Start PostgreSQL deployment:
   docker compose -f docker-compose.selfhost.yml -f docker-compose.selfhost.postgres.yml --env-file .env up -d --build
5. Optional HTTPS reverse proxy:
   docker compose -f docker-compose.selfhost.yml -f docker-compose.selfhost.postgres.yml -f docker-compose.selfhost.proxy.yml --env-file .env up -d --build
"""
    (dst / "DEPLOY_SELFHOST.txt").write_text(text, encoding="utf-8", newline="\n")


def _normalize_bundle_shell_scripts(bundle_dir: Path) -> None:
    tools_dir = bundle_dir / "tools"
    if not tools_dir.exists():
        return
    for path in tools_dir.rglob("*.sh"):
        if not path.is_file():
            continue
        original = path.read_bytes()
        normalized = original.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if normalized != original:
            path.write_bytes(normalized)


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
    parser.add_argument(
        "--include-public-downloads",
        action="store_true",
        help="Include public-downloads/ in the self-host bundle. Disabled by default to keep deploy syncs small.",
    )
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
    if args.include_public_downloads:
        _copy_public_downloads_for_bundle(PROJECT_ROOT / "public-downloads", bundle_dir / "public-downloads")

    for rel_file in (
        ".dockerignore",
        ".env.selfhost.example",
        ".env.selfhost.sync.example",
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
    _normalize_bundle_shell_scripts(bundle_dir)

    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)

    print(f"Self-host bundle directory: {bundle_dir}")
    print(f"Self-host bundle zip: {zip_path}")
    if args.include_public_downloads:
        print("Included optional public-downloads/ assets in the bundle.")
    else:
        print("Skipped optional public-downloads/ assets to keep the deploy bundle smaller.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
