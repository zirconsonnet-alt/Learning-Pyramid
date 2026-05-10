import os
import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    host = (os.getenv("LEARNINGPYRAMID_BIND_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = int((os.getenv("LEARNINGPYRAMID_PORT") or "8001").strip() or "8001")
    proxy_headers = _env_bool("LEARNINGPYRAMID_PROXY_HEADERS", True)
    forwarded_allow_ips = (os.getenv("LEARNINGPYRAMID_FORWARDED_ALLOW_IPS") or "127.0.0.1").strip() or "127.0.0.1"

    uvicorn.run(
        "adapter.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
