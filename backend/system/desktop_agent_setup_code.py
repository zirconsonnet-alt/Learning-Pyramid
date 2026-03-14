from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


SETUP_CODE_PREFIX = "LPDA1"


@dataclass(frozen=True, slots=True)
class DesktopAgentSetupCode:
    server_url: str
    setup_token: str


def encode_desktop_agent_setup_code(*, server_url: str, setup_token: str) -> str:
    normalized_server_url = str(server_url).strip().rstrip("/")
    normalized_setup_token = str(setup_token).strip()
    if not normalized_server_url:
        raise PreconditionFailure("desktop agent setup code requires server_url")
    if not normalized_setup_token:
        raise PreconditionFailure("desktop agent setup code requires setup_token")
    payload = {
        "v": 1,
        "serverUrl": normalized_server_url,
        "setupToken": normalized_setup_token,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{SETUP_CODE_PREFIX}.{encoded}"


def decode_desktop_agent_setup_code(value: str) -> DesktopAgentSetupCode:
    raw_value = str(value).strip()
    prefix = f"{SETUP_CODE_PREFIX}."
    if not raw_value.startswith(prefix):
        raise PreconditionFailure("desktop agent setup code prefix is invalid")
    encoded = raw_value[len(prefix) :].strip()
    if not encoded:
        raise PreconditionFailure("desktop agent setup code payload is missing")
    padded = encoded + "=" * ((4 - (len(encoded) % 4)) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise PreconditionFailure("desktop agent setup code payload is invalid") from exc
    if not isinstance(payload, dict):
        raise PreconditionFailure("desktop agent setup code payload is invalid")
    server_url = str(payload.get("serverUrl") or "").strip().rstrip("/")
    setup_token = str(payload.get("setupToken") or "").strip()
    if int(payload.get("v") or 0) != 1:
        raise PreconditionFailure("desktop agent setup code version is invalid")
    if not server_url:
        raise PreconditionFailure("desktop agent setup code server_url is missing")
    if not setup_token:
        raise PreconditionFailure("desktop agent setup code setup_token is missing")
    return DesktopAgentSetupCode(server_url=server_url, setup_token=setup_token)
