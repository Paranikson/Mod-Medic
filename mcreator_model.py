#!/usr/bin/env python3
"""
Normalized model of an MCreator workspace.

This is the LOADER layer: it turns MCreator's JSON into plain Python objects.
Nothing in here decides what counts as a mistake -- that comes later, in rules
that read this model. Keeping the two apart means a future MCreator version
only ever breaks this file.

Built against: mcreatorVersion 202600114619, generator neoforge-1.21.8, _fv 85.

Usage:
    python mcreator_model.py "C:\\Users\\paran\\MCreatorWorkspaces\\kgm_manual"
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Which textures/ subfolder an element type looks in.
TEXTURE_FOLDERS = {
    "block": ["block"],
    "dimension": ["block", "item"],
    "item": ["item"],
    "tool": ["item"],
    "livingentity": ["entities", "item"],
}

@dataclass
class Reference:
    """One element pointing at another. `kind` says how it was written."""
    target: str          # "CustomGrass"
    kind: str            # "custom" | "vanilla" | "procedure"
    field_path: str      # "groundBlock.value" -- where it was found


@dataclass
class Element:
    name: str
    type: str
    registry_name: str
    compiles: bool
    locked_code: bool
    definition: dict = field(default_factory=dict)
    file_version: int | None = None

    def refs(self) -> list[Reference]:
        return collect_refs(self.definition)

    def textures(self) -> list[tuple[str, str]]:
        """[(field_name, texture_value)] for every non-empty texture field."""
        found: list[tuple[str, str]] = []

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    sub = f"{path}.{key}" if path else key
                    if "texture" in key.lower() and isinstance(value, str):
                        # Skip vanilla namespaced refs like minecraft:nether_portal
                        if value and ":" not in value:
                            found.append((sub, value))
                    else:
                        walk(value, sub)
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(self.definition)
        return found

    def procedure_xml(self) -> str | None:
        return self.definition.get("procedurexml")

    def words_used(self) -> set[str]:
        """
        Every field value inside this element's Blockly XML (procedures and
        entity AI). Used to spot which variables and elements a procedure
        actually touches, without needing to know every Blockly block type.
        """
        words: set[str] = set()
        for key in ("procedurexml", "aixml"):
            xml = self.definition.get(key)
            if not isinstance(xml, str) or not xml.strip():
                continue
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue
            for node in root.iter():
                if node.text and node.text.strip():
                    words.add(node.text.strip())
                for value in node.attrib.values():
                    words.add(value)
        return words


@dataclass
class Variable:
    name: str
    type: str
    scope: str
    value: str


@dataclass
class Workspace:
    root: Path
    modid: str
    mod_name: str
    generator: str
    mcreator_version: int
    settings: dict
    elements: list[Element]
    variables: list[Variable]
    tags: dict
    language_map: dict
    texture_files: set[str]      # "block/custome_ore.png"

    def by_name(self, name: str) -> Element | None:
        return next((e for e in self.elements if e.name == name), None)

    def of_type(self, etype: str) -> list[Element]:
        return [e for e in self.elements if e.type == etype]

    @property
    def element_names(self) -> set[str]:
        return {e.name for e in self.elements}

    @property
    def variable_names(self) -> set[str]:
        return {v.name for v in self.variables}

    def has_texture(self, etype: str, value: str) -> bool:
        folders = TEXTURE_FOLDERS.get(etype, ["item", "block", "entities"])
        name = value if value.lower().endswith(".png") else f"{value}.png"
        return any(f"{folder}/{name}" in self.texture_files for folder in folders)

def collect_refs(definition: dict) -> list[Reference]:
    """
    Walk a definition and pull out every outgoing reference.

    Two shapes matter:
      {"value": "CUSTOM:CustomGrass"}  -> another mod element
      {"value": "Blocks.GRAVEL"}       -> vanilla
      {"name": "VictoryProcedure"}     -> a procedure hook
    """
    refs: list[Reference] = []

    def walk(node, path=""):
        if isinstance(node, dict):
            raw = node.get("value")
            if isinstance(raw, str) and raw:
                target = re.sub(r"^~?CUSTOM:", "", raw)
                kind = "custom" if target != raw else "vanilla"
                refs.append(Reference(target, kind, f"{path}.value".lstrip(".")))
            hook = node.get("name")
            if isinstance(hook, str) and hook and set(node.keys()) == {"name"}:
                refs.append(Reference(hook, "procedure", f"{path}.name".lstrip(".")))
            for key, value in node.items():
                if key not in ("value", "name"):
                    walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(definition)
    return refs


def load(path: str | Path) -> Workspace:
    root = Path(path).expanduser().resolve()

    # is_file() matters: there is also a hidden ".mcreator" cache FOLDER.
    candidates = [p for p in root.glob("*.mcreator") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No .mcreator file in {root}")
    data = json.loads(candidates[0].read_text(encoding="utf-8"))

    settings = data.get("workspaceSettings", {})
    modid = settings.get("modid", "")

    elements: list[Element] = []
    elements_dir = root / "elements"
    for entry in data.get("mod_elements", []):
        name = entry.get("name", "")
        definition: dict = {}
        fv = None
        mod_file = elements_dir / f"{name}.mod.json"
        if mod_file.exists():
            raw = json.loads(mod_file.read_text(encoding="utf-8"))
            definition = raw.get("definition", {})
            fv = raw.get("_fv")
        elements.append(Element(
            name=name,
            type=entry.get("type", ""),
            registry_name=entry.get("registry_name", ""),
            compiles=bool(entry.get("compiles", True)),
            locked_code=bool(entry.get("locked_code", False)),
            definition=definition,
            file_version=fv,
        ))

    variables = [
        Variable(v.get("name", ""), v.get("type", ""), v.get("scope", ""), str(v.get("value", "")))
        for v in data.get("variable_elements", [])
    ]

    textures_root = root / "src" / "main" / "resources" / "assets" / modid / "textures"
    texture_files = set()
    if textures_root.is_dir():
        for png in textures_root.rglob("*.png"):
            texture_files.add("/".join(png.relative_to(textures_root).parts))

    return Workspace(
        root=root,
        modid=modid,
        mod_name=settings.get("modName", ""),
        generator=settings.get("currentGenerator", ""),
        mcreator_version=data.get("mcreatorVersion", 0),
        settings=settings,
        elements=elements,
        variables=variables,
        tags=data.get("tag_elements", {}),
        language_map=data.get("language_map", {}),
        texture_files=texture_files,
    )


def _find_mcreator_file(root: Path) -> Path:
    """
    Locate the workspace .mcreator FILE anywhere under root.

    Students who zip a folder by hand often add an extra wrapper directory,
    so we search at every depth. The hidden ".mcreator" cache directory
    matches the same glob, so is_file() is required.
    """
    candidates = [p for p in root.rglob("*.mcreator") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(
            f"No .mcreator file found under {root}. "
            "This does not look like an MCreator workspace."
        )
    # If several copies exist, pick the one closest to the top.
    candidates.sort(key=lambda p: (len(p.relative_to(root).parts), str(p).lower()))
    return candidates[0]


def load_any(path: str | Path) -> Workspace:
    """
    Load a workspace from a folder or an exported .zip.

    For a zip, extract to a temp directory, find the .mcreator file at any
    depth, load it, then delete the temp files.
    """
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Nothing exists at {source}")

    if source.is_file() and source.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="modmedic_") as tmp:
            with zipfile.ZipFile(source) as zf:
                zf.extractall(tmp)
            try:
                mcreator = _find_mcreator_file(Path(tmp))
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"No .mcreator file found inside {source.name}. "
                    "If you zipped the folder yourself, make sure the "
                    "workspace is inside it."
                ) from None
            return load(mcreator.parent)

    if source.is_dir():
        mcreator = _find_mcreator_file(source)
        return load(mcreator.parent)

    raise FileNotFoundError(
        f"{source} is not a workspace folder or a .zip file."
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    ws = load(sys.argv[1])
    print(f"{ws.mod_name} ({ws.modid})  generator={ws.generator}")
    print(f"{len(ws.elements)} elements, {len(ws.variables)} variables, "
          f"{len(ws.texture_files)} texture files\n")

    # --- Sanity check 1: does every CUSTOM: reference resolve? ---
    print("Broken references:")
    broken = 0
    for el in ws.elements:
        for ref in el.refs():
            if ref.kind in ("custom", "procedure") and ref.target not in ws.element_names:
                print(f"  {el.name}.{ref.field_path} -> {ref.target} (not found)")
                broken += 1
    print(f"  {broken} found\n")

    # --- Sanity check 2: does every texture file exist on disk? ---
    print("Missing textures:")
    missing = 0
    for el in ws.elements:
        for fname, value in el.textures():
            if not ws.has_texture(el.type, value):
                print(f"  {el.name}.{fname} -> {value} (no file)")
                missing += 1
    print(f"  {missing} found\n")

    # --- Sanity check 3: duplicate display names in the language map ---
    print("Duplicate display names:")
    seen: dict[str, list[str]] = {}
    for key, label in ws.language_map.get("en_us", {}).items():
        seen.setdefault(label, []).append(key)
    for label, keys in seen.items():
        if len(keys) > 1:
            print(f"  \"{label}\" used by {len(keys)}: {', '.join(keys)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
