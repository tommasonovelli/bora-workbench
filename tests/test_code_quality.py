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
_PARAMETER_EXCEPTIONS: dict[str, str] = {}


class _QualifiedDefinitionVisitor(ast.NodeVisitor):
    """Collect functions with their class or enclosing-function qualification."""

    def __init__(self) -> None:
        """Create one visitor with no collected definitions."""
        self.definitions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
        self._names: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Include a class name while visiting its methods."""
        self._visit_named(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Record a synchronous function and visit nested definitions."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Record an asynchronous function and visit nested definitions."""
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Record one qualified function before descending into it."""
        qualified_name = ".".join([*self._names, node.name])
        self.definitions.append((qualified_name, node))
        self._visit_named(node)

    def _visit_named(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit one named scope while maintaining its qualification stack."""
        self._names.append(node.name)
        self.generic_visit(node)
        self._names.pop()


def _python_files() -> Iterator[Path]:
    """Yield every hand-written Python file governed by AGENTS.md."""
    for root in _SOURCE_ROOTS:
        yield from sorted((_ROOT / root).rglob("*.py"))


def _definitions(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function and method, including nested test helpers."""
    visitor = _QualifiedDefinitionVisitor()
    visitor.visit(tree)
    for _, node in visitor.definitions:
        yield node


def _qualified_definitions(
    tree: ast.AST,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield every function with its stable source qualification."""
    visitor = _QualifiedDefinitionVisitor()
    visitor.visit(tree)
    yield from visitor.definitions


def _parameter_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count explicit production parameters except the method receiver."""
    parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    count = sum(parameter.arg not in {"self", "cls"} for parameter in parameters)
    return count + int(node.args.vararg is not None) + int(node.args.kwarg is not None)


def _parameter_failures(sources: dict[str, str], exceptions: dict[str, str]) -> list[str]:
    """Return over-limit, malformed-exception, and stale-exception failures."""
    failures = [f"{key} has no reason" for key, reason in exceptions.items() if not reason.strip()]
    used: set[str] = set()
    for relative, source in sources.items():
        for qualified_name, node in _qualified_definitions(ast.parse(source)):
            count = _parameter_count(node)
            if count <= 3:
                continue
            key = f"{relative}::{qualified_name}"
            if key in exceptions:
                used.add(key)
            else:
                failures.append(f"{relative}:{node.lineno} has {count} parameters")
    failures.extend(f"{key} is stale" for key in sorted(exceptions.keys() - used))
    return failures


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
    """Limit production interfaces except for narrow, justified registrations."""
    sources = {
        path.relative_to(_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in (_ROOT / "src").rglob("*.py")
    }
    assert _parameter_failures(sources, _PARAMETER_EXCEPTIONS) == []


def test_parameter_exceptions_must_be_necessary_and_explained() -> None:
    """Reject missing, unexplained, and stale parameter-limit registrations."""
    source = "def publish(one, two, three, four):\n    return one\n"
    key = "src/example.py::publish"
    assert _parameter_failures({"src/example.py": source}, {})
    assert _parameter_failures({"src/example.py": source}, {key: "published callback"}) == []
    stale_source = "def publish(one, two, three):\n    return one\n"
    assert _parameter_failures({"src/example.py": stale_source}, {key: "published callback"})
    assert _parameter_failures({"src/example.py": source}, {key: ""})


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
