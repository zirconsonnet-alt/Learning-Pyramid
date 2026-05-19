import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "learningpyramid_selfhost_ed25519"


REMOTE_HEALTH_SCRIPT = r'''
set -u

REMOTE_ROOT="$1"
cd "$REMOTE_ROOT/app" || exit 2

compose_selfhost() {
  docker compose \
    -f docker-compose.selfhost.yml \
    -f docker-compose.selfhost.postgres.yml \
    --env-file .env "$@"
}

APP_ID="$(compose_selfhost ps -q app 2>/dev/null | tail -n 1 || true)"
STATUS=""
HEALTH=""
LIVE_OK=0
CAPABILITIES_OK=0

if [ -n "$APP_ID" ]; then
  STATUS="$(docker inspect -f '{{.State.Status}}' "$APP_ID" 2>/dev/null | tr -d '\r' || true)"
  HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$APP_ID" 2>/dev/null | tr -d '\r' || true)"
fi

PUBLIC_HOST="$(grep '^LEARNINGPYRAMID_PUBLIC_HOST=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r' | xargs || true)"
TRUSTED_HOSTS="$(grep '^LEARNINGPYRAMID_TRUSTED_HOSTS=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r' | xargs || true)"
HOST_HEADER="$PUBLIC_HOST"
if [ -z "$HOST_HEADER" ] && [ -n "$TRUSTED_HOSTS" ]; then
  HOST_HEADER="$(printf '%s' "$TRUSTED_HOSTS" | cut -d, -f1 | xargs)"
fi
if [ -z "$HOST_HEADER" ]; then
  HOST_HEADER="localhost"
fi

if curl -fsS -H "Host: $HOST_HEADER" http://127.0.0.1:8001/api/health/live >/dev/null 2>&1; then
  LIVE_OK=1
fi
if curl -fsS -H "Host: $HOST_HEADER" http://127.0.0.1:8001/api/system/capabilities >/dev/null 2>&1; then
  CAPABILITIES_OK=1
fi

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if [ "$LIVE_OK" = "1" ]; then
  LIVE_JSON=true
else
  LIVE_JSON=false
fi
if [ "$CAPABILITIES_OK" = "1" ]; then
  CAPABILITIES_JSON=true
else
  CAPABILITIES_JSON=false
fi

printf '{"appContainerId":"%s","status":"%s","health":"%s","liveOk":%s,"capabilitiesOk":%s,"hostHeader":"%s"}\n' \
  "$(json_escape "$APP_ID")" \
  "$(json_escape "$STATUS")" \
  "$(json_escape "$HEALTH")" \
  "$LIVE_JSON" \
  "$CAPABILITIES_JSON" \
  "$(json_escape "$HOST_HEADER")"
'''


REMOTE_LOGS_SCRIPT = r'''
set -u

REMOTE_ROOT="$1"
SINCE="$2"
cd "$REMOTE_ROOT/app" || exit 2

compose_selfhost() {
  docker compose \
    -f docker-compose.selfhost.yml \
    -f docker-compose.selfhost.postgres.yml \
    --env-file .env "$@"
}

LOGS="$(compose_selfhost logs --since "$SINCE" app 2>/dev/null || true)"
SEGMENT_COUNT="$(printf '%s\n' "$LOGS" | grep -c '/segments/' || true)"
DIRECT_COUNT="$(printf '%s\n' "$LOGS" | grep -c 'baidu-direct-playback' || true)"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

printf '{"since":"%s","serverSegmentRequestCount":%s,"baiduDirectPlaybackRequestCount":%s}\n' \
  "$(json_escape "$SINCE")" \
  "$SEGMENT_COUNT" \
  "$DIRECT_COUNT"
'''


REMOTE_PLAYBACK_SCRIPT = r'''
set -u

REMOTE_ROOT="$1"
SUBJECT_ID="$2"
SCOPED_PROJECT_ID="$3"
INSTANCE_IDS_JSON="$4"
SAMPLE_LIMIT="$5"
INSTANCE_LIMIT="$6"

cd "$REMOTE_ROOT/app" || exit 2

docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  exec -T app python - "$SUBJECT_ID" "$SCOPED_PROJECT_ID" "$INSTANCE_IDS_JSON" "$SAMPLE_LIMIT" "$INSTANCE_LIMIT" <<'PY'
import json
import re
import sys
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from adapter.deps import get_api, get_auth_store
from backend.models.enums import MaterialSourceKind
from backend.system.auth_store import decrypt_secret_value


REQUEST_TIMEOUT = 20
MAX_PLAYLIST_BYTES = 1024 * 1024
MAX_SAMPLE_BYTES = 4096
TOKEN_RE = re.compile(r"(access_token=)[^&\s]+")


def redact(value: object) -> str:
    text = str(value)
    return TOKEN_RE.sub(r"\1[REDACTED]", text)


def enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def is_allowed_baidu_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and (
            host == "baidu.com"
            or host.endswith(".baidu.com")
            or host == "baidupcs.com"
            or host.endswith(".baidupcs.com")
            or host == "bdstatic.com"
            or host.endswith(".bdstatic.com")
        )
    )


def query_keys(value: str) -> list[str]:
    parsed = urlparse(value)
    return sorted(parse_qs(parsed.query, keep_blank_values=True).keys())


def looks_signed_baidu_media_url(value: str) -> bool:
    query = parse_qs(urlparse(value).query, keep_blank_values=True)
    if "access_token" in query:
        return False
    if "sign" in query and ("fid" in query or "fsid" in query):
        return True
    if "xcode" in query and ("fid" in query or "fsid" in query):
        return True
    return False


def signed_query_has_access_token(value: str) -> bool:
    query = parse_qs(urlparse(value).query, keep_blank_values=True)
    signed_markers = ("sign" in query or "xcode" in query) and ("fid" in query or "fsid" in query)
    return bool(signed_markers and "access_token" in query)


def url_info(value: str) -> dict[str, object]:
    parsed = urlparse(value)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or "",
        "pathSuffix": parsed.path[-48:],
        "queryKeys": query_keys(value),
        "allowedHost": is_allowed_baidu_url(value),
        "signedBaiduMediaUrl": looks_signed_baidu_media_url(value),
        "signedUrlHasAccessToken": signed_query_has_access_token(value),
    }


def playlist_uris(text: str, base_url: str) -> list[str]:
    out: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(urljoin(base_url, line))
    return out


def read_limited(response: requests.Response, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        remaining = max(0, limit - total)
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        total += min(len(chunk), remaining)
        if total >= limit:
            break
    return b"".join(chunks)


def fetch_bytes(value: str, *, range_header: str | None, limit: int) -> dict[str, object]:
    headers = {"User-Agent": "LearningPyramidDesktopMvpVerifier/1.0"}
    if range_header:
        headers["Range"] = range_header
    try:
        response = requests.get(
            value,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            allow_redirects=True,
        )
        try:
            body = read_limited(response, limit)
        finally:
            response.close()
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "byteCount": 0,
            "contentType": "",
            "finalHost": "",
            "error": redact(exc),
        }
    return {
        "ok": response.status_code in {200, 206} and len(body) > 0,
        "status": int(response.status_code),
        "byteCount": len(body),
        "contentType": str(response.headers.get("content-type") or ""),
        "finalHost": urlparse(response.url).hostname or "",
        "startsWithExtm3u": body.lstrip().startswith(b"#EXTM3U"),
        "textPrefix": body[:80].decode("utf-8", errors="ignore"),
    }


def fetch_text(value: str, *, limit: int) -> tuple[dict[str, object], str]:
    probe = fetch_bytes(value, range_header=None, limit=limit)
    text = str(probe.get("textPrefix") or "")
    if probe.get("ok"):
        try:
            response = requests.get(
                value,
                headers={"User-Agent": "LearningPyramidDesktopMvpVerifier/1.0"},
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True,
            )
            try:
                body = read_limited(response, limit)
            finally:
                response.close()
            probe = {
                "ok": response.status_code in {200, 206} and len(body) > 0,
                "status": int(response.status_code),
                "byteCount": len(body),
                "contentType": str(response.headers.get("content-type") or ""),
                "finalHost": urlparse(response.url).hostname or "",
                "startsWithExtm3u": body.lstrip().startswith(b"#EXTM3U"),
            }
            text = body.decode("utf-8", errors="replace")
        except Exception as exc:
            probe = {
                "ok": False,
                "status": None,
                "byteCount": 0,
                "contentType": "",
                "finalHost": "",
                "error": redact(exc),
            }
            text = ""
    return probe, text


def is_playlist_url(value: str) -> bool:
    path = urlparse(value).path.lower()
    return path.endswith(".m3u8") or ".m3u8" in path


def collect_segment_samples(
    text: str,
    base_url: str,
    *,
    sample_limit: int,
    depth: int = 0,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    segment_samples: list[dict[str, object]] = []
    playlist_probes: list[dict[str, object]] = []
    failures: list[str] = []
    if depth > 3 or sample_limit <= 0:
        return segment_samples, playlist_probes, failures
    for target in playlist_uris(text, base_url):
        if len(segment_samples) >= sample_limit:
            break
        info = url_info(target)
        if not info["allowedHost"]:
            failures.append(f"playlist uri host is outside desktop allowlist: {info['host']}")
            continue
        if info["signedUrlHasAccessToken"]:
            failures.append(f"signed media uri has access_token appended: {info['host']}")
            continue
        if is_playlist_url(target):
            probe, nested_text = fetch_text(target, limit=MAX_PLAYLIST_BYTES)
            playlist_probes.append({"url": info, "probe": probe})
            if not probe.get("ok"):
                failures.append(f"nested playlist request failed: host={info['host']} status={probe.get('status')}")
                continue
            if not str(nested_text).lstrip().startswith("#EXTM3U"):
                failures.append(f"nested playlist content is not HLS: host={info['host']}")
                continue
            nested_segments, nested_playlists, nested_failures = collect_segment_samples(
                nested_text,
                target,
                sample_limit=sample_limit - len(segment_samples),
                depth=depth + 1,
            )
            segment_samples.extend(nested_segments)
            playlist_probes.extend(nested_playlists)
            failures.extend(nested_failures)
            continue

        probe = fetch_bytes(target, range_header="bytes=0-31", limit=MAX_SAMPLE_BYTES)
        if probe.get("startsWithExtm3u"):
            nested_text = str(probe.get("textPrefix") or "")
            nested_segments, nested_playlists, nested_failures = collect_segment_samples(
                nested_text,
                target,
                sample_limit=sample_limit - len(segment_samples),
                depth=depth + 1,
            )
            playlist_probes.append({"url": info, "probe": probe})
            segment_samples.extend(nested_segments)
            playlist_probes.extend(nested_playlists)
            failures.extend(nested_failures)
            continue
        segment_samples.append({"url": info, "probe": probe})
        if not probe.get("ok"):
            failures.append(f"segment range request failed: host={info['host']} status={probe.get('status')}")
    return segment_samples, playlist_probes, failures


def instance_row(summary: object) -> dict[str, object]:
    instance = getattr(summary, "instance")
    return {
        "instanceId": str(getattr(instance, "instance_id")),
        "materialId": getattr(instance, "material_id").as_posix(),
        "presence": enum_value(getattr(instance, "presence")),
        "mediaSourceKind": str(getattr(summary, "media_source_kind")),
        "playbackKind": str(getattr(summary, "playback_kind")),
        "durationMs": getattr(summary, "duration_ms"),
    }


def current_tree_leaf_instance_ids(api: object, internal_project_id: str) -> list[str]:
    ids: list[str] = []
    for node in api.list_learning_object_nodes(internal_project_id):
        instance_id = getattr(node, "instance_id", None)
        if instance_id is None:
            continue
        ids.append(str(instance_id))
    return ids


def verify_instance(api: object, auth_store: object, internal_project_id: str, row: dict[str, object], sample_limit: int) -> dict[str, object]:
    instance_id = str(row["instanceId"])
    failures: list[str] = []
    descriptor: dict[str, Any] | None = None
    try:
        descriptor = api.get_instance_baidu_direct_playback_descriptor(
            internal_project_id,
            instance_id,
            auth_store=auth_store,
        )
    except Exception as exc:
        failures.append(f"descriptor generation failed: {redact(exc)}")

    if descriptor is None:
        return {**row, "ok": False, "failures": failures, "uriCount": 0, "segmentSamples": []}

    playlist_text = descriptor.get("playlistText")
    upstream_url = descriptor.get("upstreamUrl")
    if not isinstance(playlist_text, str) or not playlist_text.strip():
        failures.append("descriptor playlistText is empty or not a string")
        playlist_text = ""
    if not str(playlist_text).lstrip().startswith("#EXTM3U"):
        failures.append("descriptor playlistText is not an HLS playlist")
    if "/segments/" in str(playlist_text):
        failures.append("descriptor playlistText still contains server /segments/ URLs")
    if not isinstance(upstream_url, str) or not upstream_url.strip():
        failures.append("descriptor upstreamUrl is empty or not a string")
        upstream_url = ""
    if upstream_url and not is_allowed_baidu_url(upstream_url):
        failures.append(f"descriptor upstreamUrl host is outside desktop allowlist: {urlparse(upstream_url).hostname or ''}")

    uris = playlist_uris(str(playlist_text), str(upstream_url))
    if not uris:
        failures.append("descriptor playlist has no playable URI lines")
    uri_infos = [url_info(value) for value in uris[:10]]
    for info in uri_infos:
        if not info["allowedHost"]:
            failures.append(f"playlist uri host is outside desktop allowlist: {info['host']}")
        if info["signedUrlHasAccessToken"]:
            failures.append(f"signed media uri has access_token appended: {info['host']}")

    segment_samples, playlist_probes, sample_failures = collect_segment_samples(
        str(playlist_text),
        str(upstream_url),
        sample_limit=sample_limit,
    )
    failures.extend(sample_failures)
    if not segment_samples:
        failures.append("no media segment samples were reached from playlist")

    return {
        **row,
        "ok": not failures,
        "failures": failures,
        "descriptor": {
            "sourceKind": descriptor.get("sourceKind"),
            "playbackKind": descriptor.get("playbackKind"),
            "mimeType": descriptor.get("mimeType"),
            "durationMs": descriptor.get("durationMs"),
            "upstream": url_info(str(upstream_url)),
        },
        "uriCount": len(uris),
        "uriHosts": sorted({str(info["host"]) for info in uri_infos if info.get("host")}),
        "playlistProbeCount": len(playlist_probes),
        "segmentSamples": segment_samples,
    }


def main() -> int:
    subject_id = sys.argv[1]
    scoped_project_id = sys.argv[2]
    requested_instance_ids = set(json.loads(sys.argv[3]))
    sample_limit = max(1, int(sys.argv[4]))
    instance_limit = max(1, int(sys.argv[5]))

    api = get_api()
    auth_store = get_auth_store()
    report: dict[str, object] = {
        "subjectId": subject_id,
        "scopedProjectId": scoped_project_id,
        "failures": [],
        "checkedInstances": [],
    }
    try:
        internal_project_id = str(api.resolve_scoped_project_internal_key(subject_id, scoped_project_id))
        report["internalProjectId"] = internal_project_id
        summaries = [instance_row(item) for item in api.list_instances_with_media_summary(internal_project_id)]
        report["instanceCount"] = len(summaries)
        current_leaf_ids = current_tree_leaf_instance_ids(api, internal_project_id)
        current_leaf_id_set = set(current_leaf_ids)
        report["learningObjectLeafInstanceCount"] = len(current_leaf_ids)
        row_by_id = {str(item["instanceId"]): item for item in summaries}
        if requested_instance_ids:
            selected = [item for item in summaries if str(item["instanceId"]) in requested_instance_ids]
            missing = sorted(requested_instance_ids - {str(item["instanceId"]) for item in selected})
            if missing:
                report["failures"].append(f"requested instance ids not found: {', '.join(missing)}")
        else:
            selected = [
                row_by_id[instance_id]
                for instance_id in current_leaf_ids
                if instance_id in row_by_id
                and row_by_id[instance_id]["presence"] == "PRESENT"
                and row_by_id[instance_id]["mediaSourceKind"] == MaterialSourceKind.BAIDU_NETDISK.value
                and row_by_id[instance_id]["playbackKind"] == "HLS"
            ]
            if not selected:
                selected = [
                    item
                    for item in summaries
                    if item["presence"] == "PRESENT"
                    and item["mediaSourceKind"] == MaterialSourceKind.BAIDU_NETDISK.value
                    and item["playbackKind"] == "HLS"
                ]
                report["selectionSource"] = "present_baidu_instances"
            else:
                report["selectionSource"] = "learning_object_tree"
            selected = selected[:instance_limit]
        for item in selected:
            item["inLearningObjectTree"] = str(item["instanceId"]) in current_leaf_id_set
        report["candidateCount"] = len(selected)
        if not selected:
            report["failures"].append("no PRESENT BAIDU_NETDISK HLS instances found for this scoped project")
        checked = [
            verify_instance(api, auth_store, internal_project_id, row, sample_limit)
            for row in selected
        ]
        report["checkedInstances"] = checked
        for item in checked:
            if not item.get("ok"):
                report["failures"].append(f"{item.get('instanceId')}: " + "; ".join(item.get("failures") or []))
    except Exception as exc:
        report["failures"].append(redact(exc))
    report["ok"] = not report["failures"]
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
'''


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def run_command(args: Sequence[str], *, input_text: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def run_command_lf_stdin(args: Sequence[str], *, input_text: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    normalized_input = input_text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    result = subprocess.run(
        list(args),
        input=normalized_input,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return subprocess.CompletedProcess(
        args=result.args,
        returncode=result.returncode,
        stdout=result.stdout.decode("utf-8", errors="replace"),
        stderr=result.stderr.decode("utf-8", errors="replace"),
    )


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("remote command returned empty stdout")
    return json.loads(text)


def ssh_base_args(args: argparse.Namespace) -> list[str]:
    out = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
    ]
    if args.ssh_key and Path(args.ssh_key).exists():
        out.extend(["-i", str(Path(args.ssh_key)), "-o", "IdentitiesOnly=yes"])
    if args.ssh_port:
        out.extend(["-p", str(args.ssh_port)])
    out.append(f"{args.server_user}@{args.server_host}")
    return out


def run_remote_bash(
    args: argparse.Namespace,
    script: str,
    remote_args: Sequence[str],
    *,
    timeout: int,
) -> dict[str, Any]:
    command = "bash -s -- " + " ".join(shlex.quote(str(item)) for item in remote_args)
    result = run_command_lf_stdin(ssh_base_args(args) + [command], input_text=script, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            "remote command failed with exit code "
            f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return parse_json_stdout(result.stdout)


def check_remote_health(args: argparse.Namespace) -> tuple[dict[str, Any], list[Check]]:
    payload = run_remote_bash(args, REMOTE_HEALTH_SCRIPT, [args.remote_root], timeout=90)
    checks = [
        Check(
            "remote app container",
            "PASS" if payload.get("status") == "running" and payload.get("health") == "healthy" else "FAIL",
            f"status={payload.get('status') or '-'} health={payload.get('health') or '-'}",
        ),
        Check(
            "remote live health",
            "PASS" if payload.get("liveOk") else "FAIL",
            f"Host={payload.get('hostHeader') or '-'} /api/health/live",
        ),
        Check(
            "remote capabilities",
            "PASS" if payload.get("capabilitiesOk") else "FAIL",
            f"Host={payload.get('hostHeader') or '-'} /api/system/capabilities",
        ),
    ]
    return payload, checks


def check_remote_playback(args: argparse.Namespace) -> tuple[dict[str, Any], list[Check]]:
    payload = run_remote_bash(
        args,
        REMOTE_PLAYBACK_SCRIPT,
        [
            args.remote_root,
            args.subject_id,
            args.scoped_project_id,
            json.dumps(args.instance_id, ensure_ascii=True),
            str(args.sample_limit),
            str(args.instance_limit),
        ],
        timeout=args.remote_timeout,
    )
    checked = list(payload.get("checkedInstances") or [])
    segment_probe_count = sum(len(list(item.get("segmentSamples") or [])) for item in checked if isinstance(item, dict))
    checks = [
        Check(
            "baidu direct playback descriptor",
            "PASS" if payload.get("ok") and checked else "FAIL",
            f"checkedInstances={len(checked)} failures={len(list(payload.get('failures') or []))}",
        ),
        Check(
            "baidu upstream segment probes",
            "PASS" if payload.get("ok") and segment_probe_count > 0 else "FAIL",
            f"segmentProbes={segment_probe_count}",
        ),
    ]
    return payload, checks


def check_remote_logs(args: argparse.Namespace) -> tuple[dict[str, Any], list[Check]]:
    payload = run_remote_bash(args, REMOTE_LOGS_SCRIPT, [args.remote_root, args.since], timeout=90)
    segment_count = int(payload.get("serverSegmentRequestCount") or 0)
    return payload, [
        Check(
            "server segment traffic",
            "PASS" if segment_count == 0 else "FAIL",
            f"since={payload.get('since')} /segments/={segment_count} baidu-direct-playback={payload.get('baiduDirectPlaybackRequestCount')}",
        )
    ]


def newest_matching_file(root: Path, pattern: str) -> Path | None:
    items = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return items[0] if items else None


def local_desktop_process_report() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"supported": False, "processes": [], "listeners": []}
    command = r'''
$processes = @(Get-Process -Name learningpyramid-desktop -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ Id = $_.Id; Path = $_.Path }
})
$listeners = @()
foreach ($process in $processes) {
  $listeners += @(Get-NetTCPConnection -OwningProcess $process.Id -State Listen -ErrorAction SilentlyContinue | Where-Object {
    $_.LocalAddress -eq "127.0.0.1"
  } | ForEach-Object {
    [pscustomobject]@{ LocalAddress = $_.LocalAddress; LocalPort = $_.LocalPort; OwningProcess = $_.OwningProcess }
  })
}
[pscustomobject]@{ supported = $true; processes = $processes; listeners = $listeners } | ConvertTo-Json -Depth 4
'''
    result = run_command(["powershell", "-NoProfile", "-Command", command], timeout=60)
    if result.returncode != 0:
        return {"supported": True, "processes": [], "listeners": [], "error": result.stderr.strip()}
    return parse_json_stdout(result.stdout)


def as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def check_local_desktop(args: argparse.Namespace) -> tuple[dict[str, Any], list[Check]]:
    if args.skip_local_desktop:
        return {}, [Check("local desktop artifacts", "SKIP", "skipped by --skip-local-desktop")]
    exe_path = PROJECT_ROOT / "desktop" / "src-tauri" / "target" / "release" / "learningpyramid-desktop.exe"
    nsis_path = newest_matching_file(
        PROJECT_ROOT / "desktop" / "src-tauri" / "target" / "release" / "bundle" / "nsis",
        "LearningPyramid_*_x64-setup.exe",
    )
    process_report = local_desktop_process_report()
    process_count = len(as_list(process_report.get("processes")))
    listener_count = len(as_list(process_report.get("listeners")))
    checks = [
        Check(
            "local release exe",
            "PASS" if exe_path.exists() else "FAIL",
            str(exe_path.relative_to(PROJECT_ROOT)) if exe_path.exists() else "missing desktop release exe",
        ),
        Check(
            "local NSIS installer",
            "PASS" if nsis_path is not None and nsis_path.exists() else "FAIL",
            str(nsis_path.relative_to(PROJECT_ROOT)) if nsis_path else "missing NSIS setup exe",
        ),
        Check(
            "local desktop process",
            "PASS" if process_count > 0 and listener_count > 0 else "WARN",
            f"processes={process_count} localhostListeners={listener_count}",
        ),
    ]
    return process_report, checks


def print_report(
    checks: Sequence[Check],
    *,
    playback_report: dict[str, Any] | None,
    health_report: dict[str, Any] | None,
    logs_report: dict[str, Any] | None,
    local_report: dict[str, Any] | None,
) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("Windows desktop MVP live gate")
    print()
    max_name = max(len(check.name) for check in checks) if checks else 1
    for check in checks:
        print(f"{check.status:<5} {check.name:<{max_name}}  {check.detail}")
    print()
    if playback_report:
        print("Checked Baidu instances:")
        for item in playback_report.get("checkedInstances") or []:
            if not isinstance(item, dict):
                continue
            descriptor = item.get("descriptor") if isinstance(item.get("descriptor"), dict) else {}
            upstream = descriptor.get("upstream") if isinstance(descriptor, dict) else {}
            hosts = ", ".join(item.get("uriHosts") or [])
            sample_count = len(list(item.get("segmentSamples") or []))
            print(
                f"- {item.get('instanceId')} material={item.get('materialId')} "
                f"upstreamHost={upstream.get('host') if isinstance(upstream, dict) else '-'} "
                f"uriHosts={hosts or '-'} segmentSamples={sample_count}"
                f" inTree={item.get('inLearningObjectTree')}"
            )
            failures = item.get("failures") or []
            for failure in failures:
                print(f"  failure: {failure}")
        failures = playback_report.get("failures") or []
        if failures:
            print()
            print("Playback failures:")
            for failure in failures:
                print(f"- {failure}")
    if health_report:
        print()
        print(
            "Remote: "
            f"container={health_report.get('appContainerId') or '-'} "
            f"status={health_report.get('status') or '-'} "
            f"health={health_report.get('health') or '-'}"
        )
    if logs_report:
        print(
            "Logs: "
            f"since={logs_report.get('since')} "
            f"/segments/={logs_report.get('serverSegmentRequestCount')} "
            f"baidu-direct-playback={logs_report.get('baiduDirectPlaybackRequestCount')}"
        )
    if local_report and local_report.get("listeners"):
        listeners = as_list(local_report.get("listeners"))
        ports = sorted({str(item.get("LocalPort")) for item in listeners if isinstance(item, dict)})
        print(f"Local desktop listeners: {', '.join(ports)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the live Windows desktop MVP Baidu playback gate.")
    parser.add_argument("--server-host", default="plm.xuebao.chat")
    parser.add_argument("--server-user", default="root")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--ssh-key", default=str(DEFAULT_SSH_KEY) if DEFAULT_SSH_KEY.exists() else "")
    parser.add_argument("--remote-root", default="/opt/learningpyramid")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--scoped-project-id", required=True)
    parser.add_argument("--instance-id", action="append", default=[])
    parser.add_argument("--instance-limit", type=int, default=10)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--since", default="15m")
    parser.add_argument("--remote-timeout", type=int, default=240)
    parser.add_argument("--skip-local-desktop", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = parse_args(argv)
    checks: list[Check] = []
    health_report: dict[str, Any] | None = None
    playback_report: dict[str, Any] | None = None
    logs_report: dict[str, Any] | None = None
    local_report: dict[str, Any] | None = None

    try:
        health_report, health_checks = check_remote_health(args)
        checks.extend(health_checks)
        playback_report, playback_checks = check_remote_playback(args)
        checks.extend(playback_checks)
        logs_report, log_checks = check_remote_logs(args)
        checks.extend(log_checks)
        local_report, local_checks = check_local_desktop(args)
        checks.extend(local_checks)
    except Exception as exc:
        checks.append(Check("live gate runner", "FAIL", str(exc)))

    failed = [check for check in checks if check.status == "FAIL"]
    output = {
        "ok": not failed,
        "checks": [check.__dict__ for check in checks],
        "health": health_report,
        "playback": playback_report,
        "logs": logs_report,
        "localDesktop": local_report,
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_report(
            checks,
            playback_report=playback_report,
            health_report=health_report,
            logs_report=logs_report,
            local_report=local_report,
        )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
