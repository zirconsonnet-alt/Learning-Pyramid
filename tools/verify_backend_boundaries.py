import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_PATHS = (
    "adapter",
    "adapter/routers",
    "adapter/scoped_projects.py",
    "backend/system/api.py",
)
SKIP_PARTS = {"__pycache__", ".git", ".pytest_cache", ".venv", "venv", "node_modules"}
SCOPED_ROUTE_MARKERS = (
    "/subjects/{subjectId}/projects/{scopedProjectId}",
    "/subjects/{subjectId}/projects/{projectId}",
)
APPROVED_TRANSPORT_OWNER_PATHS = {
    "adapter/scoped_projects.py",
}
APPROVED_MIGRATION_OWNER_PATHS = {
    "backend/system/api.py",
}


@dataclass(frozen=True)
class BoundaryRule:
    rule_id: str
    name: str
    owner: str
    severity: str
    rationale: str
    allowed_patterns: tuple[str, ...]
    forbidden_patterns: tuple[str, ...]
    approved_owner_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardFinding:
    rule_id: str
    severity: str
    path: str
    line: int | None
    message: str
    evidence: str


RULES: dict[str, BoundaryRule] = {
    "BBG001": BoundaryRule(
        rule_id="BBG001",
        name="Transport Boundary",
        owner="Transport Boundary",
        severity="high",
        rationale="Router modules adapt HTTP requests and responses; backend storage and private helpers stay behind approved behavior boundaries.",
        allowed_patterns=(
            "Call public SystemAPI methods",
            "Use adapter.scoped_projects for scoped identity dependency wiring",
        ),
        forbidden_patterns=(
            "api.sys",
            "api._private_helper()",
        ),
        approved_owner_paths=tuple(sorted(APPROVED_TRANSPORT_OWNER_PATHS)),
    ),
    "BBG002": BoundaryRule(
        rule_id="BBG002",
        name="Scoped Identity Boundary",
        owner="Identity Boundary",
        severity="high",
        rationale="Public scoped project ids and storage-only project keys have different meanings and must be resolved in one approved place.",
        allowed_patterns=(
            "ScopedProject = Depends(resolve_scoped_project)",
            "adapter.scoped_projects.resolve_scoped_project",
        ),
        forbidden_patterns=(
            "Scoped route uses projectId directly as a storage identity",
            "Scoped route omits resolve_scoped_project",
        ),
        approved_owner_paths=("adapter/scoped_projects.py",),
    ),
    "BBG003": BoundaryRule(
        rule_id="BBG003",
        name="Authorization Ownership Boundary",
        owner="Authorization Boundary",
        severity="high",
        rationale="User ownership is subject-level access; storage-only child project keys must not become authorization facts.",
        allowed_patterns=(
            "auth_store.add_project_owner(subject_id, user_id)",
        ),
        forbidden_patterns=(
            "auth_store.add_project_owner(internal_project_id, user_id)",
            "auth_store.add_project_owner(material_project_id, user_id)",
        ),
    ),
    "BBG004": BoundaryRule(
        rule_id="BBG004",
        name="Atomic Mutation Boundary",
        owner="Atomic Mutation Boundary",
        severity="high",
        rationale="Subject/material lifecycle mutations span multiple project stores and must publish all related state together or none of it.",
        allowed_patterns=(
            "SystemAPI subject/material lifecycle methods build and persist one complete snapshot mutation",
        ),
        forbidden_patterns=(
            "delete_project(material_project_id)",
            "begin_session(material_link.subject_id) for split lifecycle writes",
        ),
        approved_owner_paths=("backend/system/api.py",),
    ),
    "BBG005": BoundaryRule(
        rule_id="BBG005",
        name="Migration Risk Containment",
        owner="Migration Risk Boundary",
        severity="medium",
        rationale="Existing migration behavior may be documented and contained, but new fallback, shim, or compatibility paths must not spread.",
        allowed_patterns=(
            "Documented migration code in an approved owner path",
        ),
        forbidden_patterns=(
            "fallback expansion",
            "shim expansion",
            "compatibility expansion",
        ),
        approved_owner_paths=tuple(sorted(APPROVED_MIGRATION_OWNER_PATHS)),
    ),
}


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _path_from_arg(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _is_skipped(path: Path) -> bool:
    return bool(set(path.parts) & SKIP_PARTS)


def _python_files(paths: Sequence[Path], root: Path) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = _path_from_arg(raw_path, root)
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix == ".py" and not _is_skipped(path):
                out.append(path)
            continue
        if path.is_dir():
            out.extend(item for item in path.rglob("*.py") if not _is_skipped(item))
    return sorted(set(out), key=lambda item: _relative(item, root))


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        chunks: list[str] = []
        for item in node.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                chunks.append(item.value)
        return "".join(chunks)
    return None


def _router_path_from_decorator(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in {"get", "post", "patch", "put", "delete"}:
        return None
    if not isinstance(func.value, ast.Name) or func.value.id != "router":
        return None
    if not node.args:
        return None
    return _literal_text(node.args[0])


def _finding(rule_id: str, path: Path, root: Path, line: int | None, message: str, evidence: str) -> GuardFinding:
    rule = RULES[rule_id]
    return GuardFinding(
        rule_id=rule.rule_id,
        severity=rule.severity,
        path=_relative(path, root),
        line=line,
        message=message,
        evidence=evidence.strip(),
    )


def _transport_findings(path: Path, root: Path, lines: list[str]) -> list[GuardFinding]:
    rel_path = _relative(path, root)
    if not rel_path.startswith("adapter/"):
        return []
    findings: list[GuardFinding] = []
    for lineno, line in enumerate(lines, start=1):
        if re.search(r"\bapi\.sys\b", line):
            findings.append(
                _finding(
                    "BBG001",
                    path,
                    root,
                    lineno,
                    "Transport layer accesses backend storage internals directly.",
                    "api.sys",
                )
            )
        private_match = re.search(r"\bapi\._[A-Za-z0-9_]+\s*\(", line)
        if private_match:
            findings.append(
                _finding(
                    "BBG001",
                    path,
                    root,
                    lineno,
                    "Transport layer accesses a private backend helper directly.",
                    private_match.group(0),
                )
            )
    return findings


def _scoped_identity_findings(path: Path, root: Path, text: str) -> list[GuardFinding]:
    rel_path = _relative(path, root)
    if not rel_path.startswith("adapter/routers/"):
        return []
    tree = ast.parse(text, filename=str(path))
    findings: list[GuardFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            route_path = _router_path_from_decorator(decorator)
            if not route_path or not any(marker in route_path for marker in SCOPED_ROUTE_MARKERS):
                continue
            source = ast.get_source_segment(text, node) or ""
            if "resolve_scoped_project" not in source:
                findings.append(
                    _finding(
                        "BBG002",
                        path,
                        root,
                        node.lineno,
                        "Scoped project route bypasses the approved identity boundary.",
                        route_path,
                    )
                )
    return findings


def _authorization_findings(path: Path, root: Path, lines: list[str]) -> list[GuardFinding]:
    storage_identity_markers = (
        "internal_project",
        "material_project_id",
        "child_project_id",
        "storage_project",
        "legacy_global_project_id",
    )
    findings: list[GuardFinding] = []
    for lineno, line in enumerate(lines, start=1):
        if "add_project_owner(" not in line:
            continue
        if any(marker in line for marker in storage_identity_markers):
            findings.append(
                _finding(
                    "BBG003",
                    path,
                    root,
                    lineno,
                    "Authorization ownership is assigned to a storage-only project identity.",
                    line.strip(),
                )
            )
    return findings


def _atomic_mutation_findings(path: Path, root: Path, lines: list[str]) -> list[GuardFinding]:
    rel_path = _relative(path, root)
    if rel_path != "backend/system/api.py":
        return []
    split_write_markers = (
        "material_project_id",
        "child_project_id",
        "internal_project_key",
        "material_link.subject_id",
    )
    findings: list[GuardFinding] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "delete_project(" in stripped and any(marker in stripped for marker in split_write_markers):
            findings.append(
                _finding(
                    "BBG004",
                    path,
                    root,
                    lineno,
                    "Cross-project lifecycle mutation bypasses the approved atomic behavior owner.",
                    stripped,
                )
            )
        if "begin_session(" in stripped and "material_link.subject_id" in stripped:
            findings.append(
                _finding(
                    "BBG004",
                    path,
                    root,
                    lineno,
                    "Cross-project lifecycle mutation opens an independent subject session.",
                    stripped,
                )
            )
    return findings


def _migration_risk_findings(path: Path, root: Path, lines: list[str]) -> list[GuardFinding]:
    rel_path = _relative(path, root)
    if rel_path in APPROVED_MIGRATION_OWNER_PATHS:
        return []
    risk_pattern = re.compile(r"\b(fallback|shim|compatibility)\b", re.IGNORECASE)
    findings: list[GuardFinding] = []
    for lineno, line in enumerate(lines, start=1):
        match = risk_pattern.search(line)
        if not match:
            continue
        findings.append(
            _finding(
                "BBG005",
                path,
                root,
                lineno,
                "New migration or compatibility expansion is outside an approved owner path.",
                line.strip(),
            )
        )
    return findings


def verify_paths(paths: Sequence[Path], *, root: Path | None = None) -> list[GuardFinding]:
    scan_root = PROJECT_ROOT if root is None else root
    findings: list[GuardFinding] = []
    for path in _python_files(paths, scan_root):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        findings.extend(_transport_findings(path, scan_root, lines))
        findings.extend(_scoped_identity_findings(path, scan_root, text))
        findings.extend(_authorization_findings(path, scan_root, lines))
        findings.extend(_atomic_mutation_findings(path, scan_root, lines))
        findings.extend(_migration_risk_findings(path, scan_root, lines))
    return sorted(findings, key=lambda item: (item.path, item.line or 0, item.rule_id, item.evidence))


def format_findings(findings: Sequence[GuardFinding]) -> str:
    blocks: list[str] = []
    for finding in findings:
        line = "" if finding.line is None else str(finding.line)
        blocks.append(
            "\n".join(
                (
                    f"rule_id: {finding.rule_id}",
                    f"severity: {finding.severity}",
                    f"path: {finding.path}",
                    f"line: {line}",
                    f"message: {finding.message}",
                    f"evidence: {finding.evidence}",
                )
            )
        )
    return "\n\n".join(blocks)


def _default_paths(root: Path) -> tuple[Path, ...]:
    return tuple(root / path for path in DEFAULT_SCAN_PATHS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify backend architecture boundary guards.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    paths = tuple(args.paths) if args.paths else _default_paths(root)
    try:
        findings = verify_paths(paths, root=root)
    except Exception as exc:
        print(f"guard_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if findings:
        print(format_findings(findings))
        return 0 if args.report_only else 1
    print("backend boundary guards verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
