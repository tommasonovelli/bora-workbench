"""Enforce the repository's mechanical readability limits on hand-written Python."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOTS = ("src", "tests", "scripts")
_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)


def _python_files() -> Iterator[Path]:
    """Yield every hand-written Python file governed by AGENTS.md."""
    for root in _SOURCE_ROOTS:
        yield from sorted((_ROOT / root).rglob("*.py"))


def _definitions(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function and method, including nested test helpers."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _nesting_depth(node: ast.AST, current: int = 0) -> int:
    """Return the deepest control-flow nesting below one AST node."""
    depth = current + 1 if isinstance(node, _NESTING_NODES) else current
    children = [_nesting_depth(child, depth) for child in ast.iter_child_nodes(node)]
    return max([depth, *children])


def _missing_docstrings(path: Path) -> list[str]:
    """Return missing module and definition docstrings for one Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    relative = path.relative_to(_ROOT)
    failures = [] if ast.get_docstring(tree) is not None else [f"{relative}:1 module"]
    for node in ast.walk(tree):
        is_definition = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        if is_definition and ast.get_docstring(node) is None:
            failures.append(f"{relative}:{node.lineno} {node.name}")
    return failures


def test_python_files_and_functions_stay_within_size_limits() -> None:
    """Keep files at 600 lines and functions at 40 lines or fewer."""
    failures: list[str] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if len(source.splitlines()) > 600:
            failures.append(f"{path.relative_to(_ROOT)} exceeds 600 lines")
        for node in _definitions(ast.parse(source)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > 40:
                failures.append(f"{path.relative_to(_ROOT)}:{node.lineno} has {length} lines")
    assert failures == []


def test_production_functions_have_at_most_three_parameters() -> None:
    """Limit production interfaces while allowing explicit test fixture injection."""
    failures: list[str] = []
    for path in (_ROOT / "src").rglob("*.py"):
        for node in _definitions(ast.parse(path.read_text(encoding="utf-8"))):
            parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            count = sum(parameter.arg not in {"self", "cls"} for parameter in parameters)
            if count > 3:
                failures.append(f"{path.relative_to(_ROOT)}:{node.lineno} has {count} parameters")
    assert failures == []


def test_functions_have_at_most_three_control_flow_levels() -> None:
    """Prevent deeply nested control flow in production, tests, and verification scripts."""
    failures: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _definitions(tree):
            depth = max((_nesting_depth(child) for child in node.body), default=0)
            if depth > 3:
                failures.append(f"{path.relative_to(_ROOT)}:{node.lineno} has depth {depth}")
    assert failures == []


def test_every_module_class_and_function_has_a_docstring() -> None:
    """Keep intent discoverable at every Python definition boundary."""
    failures: list[str] = []
    for path in _python_files():
        failures.extend(_missing_docstrings(path))
    assert failures == []
