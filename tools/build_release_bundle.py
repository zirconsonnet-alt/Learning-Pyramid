import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system.version import APP_NAME, APP_PACKAGE_NAME, APP_VERSION


def _bundle_name() -> str:
    return f"{APP_PACKAGE_NAME}-{APP_VERSION}-windows-portable"


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=str(cwd), check=True)


def _ensure_frontend_dist(*, build_frontend: bool) -> None:
    dist_index = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if build_frontend:
        _run(["pnpm", "build"], cwd=PROJECT_ROOT / "frontend")
    if not dist_index.exists():
        raise SystemExit("frontend/dist is missing. Run `pnpm -C frontend build` first.")


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _write_release_readme(dst: Path) -> None:
    text = f"""# {APP_NAME} {APP_VERSION} release bundle

Start:

```powershell
LearningPyramid.bat
```

Stop:

```powershell
LearningPyramid-stop.bat
```

Prerequisites:

- Python 3.12+
- Installed backend dependencies from `requirements.txt`

The full project README is included as `README.md`.
"""
    (dst / "RELEASE_NOTES.txt").write_text(text, encoding="utf-8", newline="\n")


def _create_zip(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-frontend", action="store_true")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "release"))
    args = parser.parse_args()

    _ensure_frontend_dist(build_frontend=args.build_frontend)

    output_root = Path(args.output_dir).resolve()
    bundle_dir = output_root / _bundle_name()
    zip_path = output_root / f"{_bundle_name()}.zip"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    for rel_path in ("adapter", "backend", "frontend/dist", "tools"):
        src = PROJECT_ROOT / rel_path
        dst = bundle_dir / rel_path
        _copy_tree(src, dst)

    for rel_file in (
        "LearningPyramid.bat",
        "LearningPyramid-stop.bat",
        "requirements.txt",
        "README.md",
    ):
        src = PROJECT_ROOT / rel_file
        dst = bundle_dir / rel_file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    _write_release_readme(bundle_dir)
    if zip_path.exists():
        zip_path.unlink()
    _create_zip(bundle_dir, zip_path)

    print(f"Release bundle directory: {bundle_dir}")
    print(f"Release bundle zip: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
