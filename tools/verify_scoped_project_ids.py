import argparse
import json
from pathlib import Path
from typing import Any


def verify_report(report: dict[str, Any]) -> dict[str, Any]:
    blocking = list(report.get("blockingIssues") or [])
    mappings = list(report.get("mappings") or [])
    seen: set[tuple[str, str]] = set()
    duplicates: list[dict[str, str]] = []
    for item in mappings:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("subjectId") or ""), str(item.get("projectId") or ""))
        if key in seen:
            duplicates.append({"subjectId": key[0], "projectId": key[1]})
        seen.add(key)
    return {
        "ok": not blocking and not duplicates,
        "blockingIssues": blocking,
        "duplicateScopedProjectIds": duplicates,
        "projectsVerified": len(mappings),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    result = verify_report(report)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
