#!/usr/bin/env python3
"""
Mod Medic -- check an MCreator workspace for common student mistakes.

Usage:
    python cli.py <path>

<path> may be a workspace folder or an exported .zip file.
"""

from __future__ import annotations

import sys
import zipfile

from mcreator_model import load_any
from rules import Finding, Severity, run_all


def _print_group(title: str, items: list[Finding]) -> None:
    print(f"{title} ({len(items)})")
    print("-" * 40)
    for finding in items:
        if finding.element:
            print(f"  [{finding.rule_id}] {finding.element}")
        else:
            print(f"  [{finding.rule_id}]")
        print(f"      {finding.message}")
        if finding.detail:
            print(f"      {finding.detail}")
        print()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python cli.py <path>")
        print("Give me a workspace folder or a .zip file.")
        return 1

    try:
        ws = load_any(sys.argv[1])
    except FileNotFoundError as exc:
        print(f"I could not find a workspace there.\n{exc}")
        return 1
    except zipfile.BadZipFile:
        print(
            "That .zip file could not be opened. "
            "Try exporting it from MCreator again."
        )
        return 1
    except Exception as exc:
        print(f"Something went wrong while opening the workspace: {exc}")
        return 1

    print(ws.mod_name or ws.modid or ws.root.name)
    print(
        f"{len(ws.elements)} elements, {len(ws.variables)} variables, "
        f"{len(ws.texture_files)} texture files"
    )
    print()

    findings = run_all(ws)
    if not findings:
        print("No problems found. This workspace looks good -- nice work!")
        return 0

    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    infos = [f for f in findings if f.severity == Severity.INFO]

    if errors:
        _print_group("ERRORS", errors)
    if warnings:
        _print_group("WARNINGS", warnings)
    if infos:
        _print_group("INFO", infos)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
