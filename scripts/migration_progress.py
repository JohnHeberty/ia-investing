#!/usr/bin/env python3
"""Migration progress tracker for IA Investing anti-corruption layer.

Scans ``src/`` for remaining legacy imports and outputs a JSON report:

    python scripts/migration_progress.py
    python scripts/migration_progress.py --json
    python scripts/migration_progress.py --output report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

_LEGACY_MODULES = frozenset(
    {
        "database",
        "workflows",
        "agents",
        "connectors",
        "domain",
        "portfolio",
        "backtesting",
        "evaluation",
        "metrics",
        "normalization",
        "data_quality",
        "observability",
        "parsers",
        "schemas",
    }
)

_RE_IMPORT = re.compile(
    r"^\s*(?:from\s+)(\w+)"  # matches `from <module> import ...`
)

_RE_IMPORT_DIRECT = re.compile(
    r"^\s*import\s+(?:(\w+)(?:\s*,|\s*$))"  # matches `import <module>`
)


@dataclass
class LegacyImport:
    file: str
    line: int
    module: str
    full_import: str


@dataclass
class ModuleSummary:
    total_files: int
    total_imports: int
    files: list[str]


def scan(root: Path) -> list[LegacyImport]:
    findings: list[LegacyImport] = []
    src = root / "src"
    for path in sorted(src.rglob("*.py")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines):
            m = _RE_IMPORT.match(line)
            if m and m.group(1) in _LEGACY_MODULES:
                findings.append(
                    LegacyImport(
                        file=str(path.relative_to(root).as_posix()),
                        line=lineno + 1,
                        module=m.group(1),
                        full_import=line.strip(),
                    )
                )
                continue
            m = _RE_IMPORT_DIRECT.match(line)
            if m and m.group(1) in _LEGACY_MODULES:
                findings.append(
                    LegacyImport(
                        file=str(path.relative_to(root).as_posix()),
                        line=lineno + 1,
                        module=m.group(1),
                        full_import=line.strip(),
                    )
                )
    return findings


def build_report(findings: list[LegacyImport]) -> dict:
    by_module: dict[str, list[LegacyImport]] = defaultdict(list)
    for item in findings:
        by_module[item.module].append(item)

    modules = {}
    total_imports = len(findings)
    files_with_legacy = len({item.file for item in findings})

    for mod, items in sorted(by_module.items()):
        files_in_mod = sorted({item.file for item in items})
        modules[mod] = asdict(
            ModuleSummary(
                total_files=len(files_in_mod),
                total_imports=len(items),
                files=files_in_mod,
            )
        )

    return {
        "summary": {
            "total_legacy_imports": total_imports,
            "files_with_legacy_imports": files_with_legacy,
            "modules_remaining": sorted(by_module.keys()),
        },
        "modules": modules,
        "findings": [asdict(f) for f in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Track legacy import migration progress.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to file")
    args = parser.parse_args()

    root = args.root.resolve()
    findings = scan(root)
    report = build_report(findings)

    if args.json or args.output is None:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = report["summary"]
    print(
        f"\nMigration Progress — {summary['files_with_legacy_imports']} files, "
        f"{summary['total_legacy_imports']} legacy imports remain "
        f"across {len(summary['modules_remaining'])} modules."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
