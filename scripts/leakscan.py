#!/usr/bin/env python3
"""CLI entry point for the leak scan: `make leakscan`, pre-commit hook, and
`witness bundle`'s internal check all share `witness.leakscan`'s logic.

Usage:
    python scripts/leakscan.py path/to/bundle.jsonl [more.jsonl ...]
    python scripts/leakscan.py --staged

Exit codes:
    0  clean
    3  one or more violations found (disallowed key / secret-shaped string
       / prose-like field over 200 chars)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from witness.leakscan import load_allowed_keys, scan_record, scan_text_blob

_STAGED_TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg"}


def scan_jsonl_file(path: Path) -> list[str]:
    allowed_keys = load_allowed_keys()
    violations: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                violations.append(f"{path}:{lineno}: invalid JSON ({exc})")
                continue
            if not isinstance(obj, dict):
                violations.append(f"{path}:{lineno}: top-level JSON value is not an object")
                continue
            for v in scan_record(obj, allowed_keys):
                violations.append(f"{path}:{lineno}: {v}")
    return violations


def scan_staged() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return [f"could not list staged files: {exc}"]

    violations: list[str] = []
    for name in out.splitlines():
        if not name.strip():
            continue
        path = Path(name)
        if not path.exists():
            continue  # deleted file
        if path.suffix == ".jsonl":
            violations.extend(scan_jsonl_file(path))
            continue
        if path.suffix in _STAGED_TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for v in scan_text_blob(text):
                violations.append(f"{path}: {v}")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="bundle.jsonl file(s) to scan")
    parser.add_argument("--staged", action="store_true", help="scan git staged files instead")
    args = parser.parse_args(argv)

    violations: list[str] = []
    if args.staged:
        violations = scan_staged()
    elif args.paths:
        for p in args.paths:
            violations.extend(scan_jsonl_file(Path(p)))
    else:
        parser.error("provide at least one path, or use --staged")

    if violations:
        print(f"leakscan: {len(violations)} violation(s) found:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 3

    print("leakscan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
