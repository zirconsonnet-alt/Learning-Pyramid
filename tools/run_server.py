from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapter.main import app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--runtime-token", required=True)
    parser.add_argument("--runtime-mode", default="release")
    args = parser.parse_args()

    os.environ["PLM_RUNTIME_TOKEN"] = args.runtime_token
    os.environ["PLM_RUNTIME_MODE"] = args.runtime_mode

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=False,
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
