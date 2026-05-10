import argparse
import json
from pathlib import Path
from typing import Any


def _load_store(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("store must be a JSON object")
    return data


def _project_is_active(project_payload: dict[str, Any]) -> bool:
    project = dict(project_payload.get("project") or {})
    return str(project.get("state") or "") == "ACTIVE"


def _study_materials(project_payload: dict[str, Any]) -> dict[str, Any]:
    raw = project_payload.get("studyMaterials") or {}
    return raw if isinstance(raw, dict) else {}


def _subject_material_link(project_payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = project_payload.get("subjectMaterialLink")
    return raw if isinstance(raw, dict) else None


def build_migration_report(store_path: str | Path, *, mode: str = "dry-run") -> dict[str, Any]:
    path = Path(store_path)
    store = _load_store(path)
    projects = {
        str(project_id): dict(payload)
        for project_id, payload in dict(store.get("projects") or {}).items()
        if isinstance(payload, dict) and _project_is_active(payload)
    }

    subject_ids = {
        project_id
        for project_id, payload in projects.items()
        if _study_materials(payload)
        or any(
            str(dict(material).get("subjectId") or "") == project_id
            for material in _study_materials(payload).values()
            if isinstance(material, dict)
        )
    }
    linked_project_ids = {
        project_id
        for project_id, payload in projects.items()
        if _subject_material_link(payload) is not None
    }

    blocking: list[dict[str, str]] = []
    mappings: list[dict[str, str]] = []
    for project_id, payload in sorted(projects.items()):
        link = _subject_material_link(payload)
        if link is not None:
            subject_id = str(link.get("subjectId") or "").strip()
            scoped_project_id = str(link.get("projectId") or "").strip() or str(project_id)
            if not subject_id:
                blocking.append({"code": "PROJECT_WITHOUT_SUBJECT", "projectId": project_id})
                continue
            mappings.append({"internalProjectKey": project_id, "subjectId": subject_id, "projectId": scoped_project_id})
            continue
        if project_id in subject_ids:
            continue
        if project_id not in linked_project_ids:
            blocking.append({"code": "PROJECT_WITHOUT_SUBJECT", "projectId": project_id})

    return {
        "mode": mode,
        "subjectsScanned": len(subject_ids),
        "projectsScanned": len(projects),
        "projectsMigrated": len(mappings),
        "referencesMigrated": {},
        "blockingIssues": blocking,
        "mappings": mappings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="learningpyramid_store.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    mode = "apply" if args.apply else "dry-run"
    report = build_migration_report(args.store, mode=mode)
    if args.apply and report["blockingIssues"]:
        raise SystemExit("migration blocked")
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
