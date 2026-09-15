#!/usr/bin/env python3
"""
Copy a trimmed MCreator workspace into tests/fixtures/<name>/.

Keeps only what Mod Medic actually reads:
  - the *.mcreator FILE at the workspace root (not the hidden .mcreator folder)
  - the entire elements/ folder
  - src/main/resources/assets/<modid>/textures/ (all subfolders)

Usage:
    python tools/make_fixture.py <source_workspace> <fixture_name>
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"


def _find_mcreator_file(root: Path) -> Path:
    """The workspace index is a FILE named *.mcreator, not the cache directory."""
    candidates = [p for p in root.rglob("*.mcreator") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No .mcreator file found under {root}")
    candidates.sort(key=lambda p: (len(p.relative_to(root).parts), str(p).lower()))
    return candidates[0]


def folder_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} bytes"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def make_fixture(source: Path, name: str) -> Path:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Nothing exists at {source}")

    mcreator = _find_mcreator_file(source)
    ws_root = mcreator.parent
    data = json.loads(mcreator.read_text(encoding="utf-8"))
    modid = data.get("workspaceSettings", {}).get("modid", "")

    dest = FIXTURES_ROOT / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    shutil.copy2(mcreator, dest / mcreator.name)

    elements = ws_root / "elements"
    if not elements.is_dir():
        raise FileNotFoundError(f"No elements/ folder next to {mcreator}")
    shutil.copytree(elements, dest / "elements")

    textures = ws_root / "src" / "main" / "resources" / "assets" / modid / "textures"
    if textures.is_dir():
        dest_textures = dest / "src" / "main" / "resources" / "assets" / modid / "textures"
        shutil.copytree(textures, dest_textures)

    return dest


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python tools/make_fixture.py <source_workspace> <fixture_name>")
        return 1

    dest = make_fixture(Path(sys.argv[1]), sys.argv[2])
    n_files = sum(1 for p in dest.rglob("*") if p.is_file())
    size = folder_size(dest)
    print(f"{dest.relative_to(REPO_ROOT)}  {n_files} files, {format_size(size)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
