import ast
from pathlib import Path


MODULES = Path(__file__).resolve().parents[1] / "app" / "modules"


def imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or ""
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)


def test_module_layers_keep_http_queries_and_transactions_at_their_boundaries():
    for path in MODULES.glob("*/router.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for imported in imports(tree):
            assert not any(
                part in imported.split(".")
                for part in ("sqlalchemy", "sqlmodel", "redis", "models", "crud")
            ), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in (
                    "commit",
                    "rollback",
                    "execute",
                    "scalar",
                    "scalars",
                ), path
    for path in MODULES.glob("*/service.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for imported in imports(tree):
            assert "fastapi" not in imported, path
            assert imported not in ("sqlmodel", "sqlalchemy"), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("execute", "scalar", "scalars", "query", "add"), path
    for path in MODULES.glob("*/crud.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for imported in imports(tree):
            assert not any(
                part in imported.split(".") for part in ("fastapi", "schemas", "service")
            ), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("commit", "rollback", "begin"), path
    for path in MODULES.glob("*/*.py"):
        owner = path.parent.name
        for imported in imports(ast.parse(path.read_text(encoding="utf-8"))):
            parts = imported.split(".")
            if parts[:2] == ["app", "modules"] and len(parts) >= 4 and parts[2] != owner:
                assert parts[3] not in ("models", "crud"), path
