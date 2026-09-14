#!/usr/bin/env python3
"""
Dump the structure of an MCreator workspace so you can see what the JSON
really looks like before writing any validator code.

Usage:
    python inspect_workspace.py "C:\\path\\to\\WorkspaceFolder"
    python inspect_workspace.py "C:\\path\\to\\WorkspaceFolder" > dump.txt
"""

import json
import sys
from pathlib import Path

# Heavy generated folders that tell you nothing useful about the format.
SKIP_DIRS = {"build", ".gradle", "gradle", ".git", ".eclipse", "run"}


def tree(root: Path, prefix: str = "", depth: int = 0, max_depth: int = 2) -> None:
    if depth > max_depth:
        return
    try:
        entries = sorted(
            (p for p in root.iterdir() if p.name not in SKIP_DIRS),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except PermissionError:
        print(f"{prefix}[permission denied]")
        return
    for i, path in enumerate(entries):
        last = i == len(entries) - 1
        marker = "/" if path.is_dir() else ""
        print(f"{prefix}{'`-- ' if last else '|-- '}{path.name}{marker}")
        if path.is_dir():
            tree(path, prefix + ("    " if last else "|   "), depth + 1, max_depth)


def header(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def preview(obj, limit: int = 2500) -> str:
    text = json.dumps(obj, indent=2)
    if len(text) > limit:
        return text[:limit] + f"\n... [truncated, {len(text)} chars total]"
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}")
        return 1

    header(f"FOLDER TREE: {root.name}")
    tree(root)

    # --- Find the workspace file. is_file() matters: there is also a hidden
    # --- ".mcreator" CACHE FOLDER that this pattern would otherwise match.
    candidates = [p for p in root.glob("*.mcreator") if p.is_file()]
    if not candidates:
        print("\nNo .mcreator FILE found in the workspace root.")
        return 1

    ws_path = candidates[0]
    header(f"READING: {ws_path.name}")
    workspace = json.loads(ws_path.read_text(encoding="utf-8"))

    print("Top-level keys:")
    for key, value in workspace.items():
        kind = type(value).__name__
        size = f" (len {len(value)})" if isinstance(value, (list, dict, str)) else ""
        print(f"  {key}: {kind}{size}")

    # --- Everything except the giant element list, printed in full ---
    header("WORKSPACE METADATA (everything except mod_elements)")
    meta = {k: v for k, v in workspace.items() if k != "mod_elements"}
    print(preview(meta, 6000))

    # --- Mod elements index ---
    elements = workspace.get("mod_elements", [])
    header(f"MOD ELEMENTS: {len(elements)} total")
    by_type: dict[str, list[dict]] = {}
    for el in elements:
        by_type.setdefault(str(el.get("type", "?")), []).append(el)
    for etype, items in sorted(by_type.items()):
        names = ", ".join(str(i.get("name", "?")) for i in items[:6])
        more = f" (+{len(items) - 6} more)" if len(items) > 6 else ""
        print(f"  {etype:<20} {len(items):>3}   {names}{more}")

    header("ONE INDEX ENTRY PER ELEMENT TYPE")
    for etype, items in sorted(by_type.items()):
        print(f"\n--- {etype} ---")
        print(preview(items[0], 1200))

    # --- The per-element files, where the real settings live ---
    elements_dir = root / "elements"
    header("ONE FULL ELEMENT FILE PER TYPE (elements/*.mod.json)")
    if not elements_dir.is_dir():
        print("No elements/ folder found.")
    else:
        for etype, items in sorted(by_type.items()):
            name = str(items[0].get("name", ""))
            path = elements_dir / f"{name}.mod.json"
            print(f"\n--- {etype}: {path.name} ---")
            if path.exists():
                text = path.read_text(encoding="utf-8")
                print(text[:3000])
                if len(text) > 3000:
                    print(f"... [truncated, {len(text)} chars total]")
            else:
                print("NOT FOUND -- naming differs, see elements/ in the tree above")

    # --- Where do textures actually live? Search everywhere except run/build ---
    header("WHERE THE .PNG FILES LIVE (grouped by folder)")
    folders: dict[str, int] = {}
    for png in root.rglob("*.png"):
        parts = png.relative_to(root).parts
        if any(d in parts for d in SKIP_DIRS):
            continue
        folder = "/".join(parts[:-1]) or "."
        folders[folder] = folders.get(folder, 0) + 1
    if not folders:
        print("  No .png files found outside skipped folders.")
    for folder, count in sorted(folders.items()):
        print(f"  {count:>4} png   {folder}/")

    header("SAMPLE TEXTURE FILENAMES")
    shown = 0
    for png in sorted(root.rglob("*.png")):
        parts = png.relative_to(root).parts
        if any(d in parts for d in SKIP_DIRS):
            continue
        print(f"  {png.relative_to(root)}")
        shown += 1
        if shown >= 40:
            print("  ...")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
