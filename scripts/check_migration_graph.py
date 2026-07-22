#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


def literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"missing {name}")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "migrations/versions")
    revisions: dict[str, Path] = {}
    parents: dict[str, tuple[str, ...]] = {}
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = literal_assignment(tree, "revision")
        down = literal_assignment(tree, "down_revision")
        try:
            dependency = literal_assignment(tree, "depends_on")
        except ValueError:
            dependency = None
        if revision in revisions:
            raise SystemExit(f"duplicate revision {revision}: {revisions[revision]} and {path}")
        revisions[revision] = path
        values: list[str] = []
        if isinstance(down, str):
            values.append(down)
        elif down is not None:
            values.extend(down)
        if isinstance(dependency, str):
            values.append(dependency)
        elif dependency is not None:
            values.extend(dependency)
        parents[revision] = tuple(dict.fromkeys(values))

    missing = sorted({parent for values in parents.values() for parent in values if parent not in revisions})
    if missing:
        print("Missing parent revisions:", ", ".join(missing))
        return 1

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(revision: str) -> None:
        if revision in visiting:
            raise RuntimeError(f"migration cycle detected at {revision}")
        if revision in visited:
            return
        visiting.add(revision)
        for parent in parents[revision]:
            visit(parent)
        visiting.remove(revision)
        visited.add(revision)

    try:
        for revision in revisions:
            visit(revision)
    except RuntimeError as exc:
        print(exc)
        return 1

    children = {revision: set() for revision in revisions}
    for revision, values in parents.items():
        for parent in values:
            if parent in children:
                children[parent].add(revision)
    heads = sorted(revision for revision, values in children.items() if not values)

    print("Heads:", ", ".join(heads))
    if heads != ["b4c000000002"]:
        print("Expected a single consolidated head: b4c000000002")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
