# LearningPyramid v1beta

LearningPyramid 是一个本地优先的学习系统，用于围绕你自己的视频或音频材料构建复述点、复习链，以及 ASR 转写产物。

## Release mode

This repository now supports a production-style local launch:

1. Install Python 3.12+
2. Install backend dependencies

```powershell
pip install -r requirements.txt
```

3. Build the frontend once

```powershell
cd frontend
pnpm install
pnpm build
cd ..
```

4. Start LearningPyramid

```powershell
LearningPyramid.bat
```

The release launcher starts a single backend process on `http://127.0.0.1:8001/` and serves the built frontend directly from FastAPI. It does not use Vite dev server and does not kill unrelated local processes.

## Build release bundle

To assemble a portable release folder and zip:

```powershell
python tools/build_release_bundle.py
```

If you want the script to rebuild the frontend first:

```powershell
python tools/build_release_bundle.py --build-frontend
```

## Build standalone Windows executables

To produce `LearningPyramid.exe`, `LearningPyramid-server.exe`, and `LearningPyramid-stop.exe`:

```powershell
python tools/build_windows_standalone.py
```

To build them in a clean packaging venv, which avoids bundling unrelated Python packages from your current environment:

```powershell
python tools/build_windows_standalone.py --bootstrap-packaging-venv
```

If you want to recreate that packaging venv from scratch:

```powershell
python tools/build_windows_standalone.py --bootstrap-packaging-venv --refresh-packaging-venv
```

## Build Windows installer package

To generate an installable bundle with `Install-LearningPyramid.bat`:

```powershell
python tools/build_windows_installer.py --bootstrap-packaging-venv
```

If Inno Setup 6 is installed, the same script also emits a `LearningPyramid-...-Setup.exe`. Otherwise it still produces a script-based installer zip.

## Stop

```powershell
LearningPyramid-stop.bat
```

## Dev mode

If you still need hot reload and Vite dev server:

```powershell
LearningPyramid.dev.bat
```

## Data location

By default, user data is stored under:

- Windows: `%LOCALAPPDATA%\LearningPyramid\plm_store.json`
- macOS: `~/Library/Application Support/LearningPyramid/plm_store.json`
- Linux: `~/.local/share/learningpyramid/plm_store.json`

Overrides:

- `PLM_STORE_PATH`: full path to the JSON store file
- `PLM_DATA_DIR`: base directory for LearningPyramid runtime data
- `PLM_PROJECTS_ROOT`: root directory used when creating new projects; default is `LearningPyramid/data`
- `PLM3_WHISPER_PYTHON`: legacy override for the Python interpreter used by the local Whisper runtime

If an older repo-local `.plm_store.json` exists and no new store exists yet, LearningPyramid copies it into the user data directory on first start. Existing `%LOCALAPPDATA%\PLM3\plm_store.json` and `%LOCALAPPDATA%\学习金字塔\plm_store.json` will also be migrated automatically.

## Whisper

ASR service selection works like this:

1. If `ProjectConfig.external_services.asr` is configured, LearningPyramid uses that service first.
2. If no ASR service is configured, LearningPyramid tries to auto-discover and launch a local Whisper runtime.
3. If neither an explicit service nor a local Whisper runtime is available, ASR requests fail with a precondition error.

The current Windows default search path for local Whisper includes:

- `H:\whisper\.venv\Scripts\python.exe`

You can override local Whisper detection with:

```powershell
set PLM3_WHISPER_PYTHON=H:\whisper\.venv\Scripts\python.exe
```

`ffmpeg` must also be available in `PATH`.
