import argparse
import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _python_files(paths: tuple[Path, ...]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            out.append(path)
        elif path.is_dir():
            out.extend(sorted(item for item in path.rglob("*.py") if "__pycache__" not in item.parts))
    return out


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


def _verify_router_paths() -> list[str]:
    issues: list[str] = []
    for path in _python_files((PROJECT_ROOT / "adapter" / "routers",)):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route_path = _router_path_from_decorator(decorator)
                if route_path and (route_path == "/projects" or route_path.startswith("/projects/")):
                    issues.append(f"{_relative(path)}:{node.lineno} legacy project route {route_path}")
    return issues


def _verify_no_scoped_middleware_rewrite() -> list[str]:
    issues: list[str] = []
    main_path = PROJECT_ROOT / "adapter" / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            target = node.value
            key = node.slice
            if isinstance(target, ast.Attribute) and target.attr == "scope":
                text = _literal_text(key)
                if text in {"path", "raw_path"}:
                    issues.append(f"{_relative(main_path)}:{node.lineno} middleware mutates request.scope[{text!r}]")
            if isinstance(target, ast.Name) and target.id == "scope":
                text = _literal_text(key)
                if text in {"path", "raw_path"}:
                    issues.append(f"{_relative(main_path)}:{node.lineno} middleware mutates scope[{text!r}]")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    sub_target = target.value
                    key = target.slice
                    text = _literal_text(key)
                    if text in {"path", "raw_path"} and (
                        (isinstance(sub_target, ast.Attribute) and sub_target.attr == "scope")
                        or (isinstance(sub_target, ast.Name) and sub_target.id == "scope")
                    ):
                        issues.append(f"{_relative(main_path)}:{node.lineno} middleware rewrites request path")
    return issues


def _verify_no_internal_project_api_urls() -> list[str]:
    issues: list[str] = []
    for path in _python_files((PROJECT_ROOT / "backend", PROJECT_ROOT / "adapter")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "/api/projects" in line:
                issues.append(f"{_relative(path)}:{lineno} contains legacy /api/projects API path")
    return issues


def verify_scoped_project_routes() -> list[str]:
    return [
        *_verify_router_paths(),
        *_verify_no_scoped_middleware_rewrite(),
        *_verify_no_internal_project_api_urls(),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    issues = verify_scoped_project_routes()
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("scoped project routes verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
