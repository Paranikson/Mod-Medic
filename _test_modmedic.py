#!/usr/bin/env python3
"""Throwaway checks for rules.py, cli.py, and load_any()."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from mcreator_model import Element, Variable, Workspace, load_any
from rules import (
    ALL_RULES,
    Severity,
    e001_element_does_not_compile,
    e002_missing_element_ref,
    e003_missing_procedure_hook,
    e004_missing_texture,
    run_all,
    w001_duplicate_display_names,
    w002_procedure_never_used,
    w003_variable_never_used,
    w004_no_display_name,
)


def ws(**kwargs) -> Workspace:
    defaults = dict(
        root=Path("."),
        modid="testmod",
        mod_name="Test Mod",
        generator="neoforge-1.21.8",
        mcreator_version=202600114619,
        settings={},
        elements=[],
        variables=[],
        tags={},
        language_map={},
        texture_files=set(),
    )
    defaults.update(kwargs)
    return Workspace(**defaults)


def xml_with(*words: str) -> str:
    fields = "".join(f"<field>{w}</field>" for w in words)
    return f"<xml><block>{fields}</block></xml>"


def test_e001():
    broken = Element("BadBlock", "block", "bad_block", compiles=False, locked_code=False)
    ok = Element("GoodBlock", "block", "good_block", compiles=True, locked_code=False)
    findings = e001_element_does_not_compile(ws(elements=[broken, ok]))
    assert len(findings) == 1
    assert findings[0].rule_id == "E001"
    assert findings[0].element == "BadBlock"
    assert "BadBlock has an error inside it" in findings[0].message


def test_e002():
    el = Element(
        "Biome", "biome", "biome", True, False,
        definition={"groundBlock": {"value": "CUSTOM:MissingDirt"}},
    )
    present = Element("Stone", "block", "stone", True, False)
    findings = e002_missing_element_ref(ws(elements=[el, present]))
    assert len(findings) == 1
    assert findings[0].rule_id == "E002"
    assert "MissingDirt" in findings[0].message

    ok = Element(
        "Biome", "biome", "biome", True, False,
        definition={"groundBlock": {"value": "CUSTOM:Stone"}},
    )
    assert e002_missing_element_ref(ws(elements=[ok, present])) == []


def test_e003():
    el = Element(
        "Sword", "tool", "sword", True, False,
        definition={"onRightClicked": {"name": "MissingProc"}},
    )
    findings = e003_missing_procedure_hook(ws(elements=[el]))
    assert len(findings) == 1
    assert findings[0].rule_id == "E003"
    assert "MissingProc" in findings[0].message

    proc = Element("DoThing", "procedure", "do_thing", True, False)
    hooked = Element(
        "Sword", "tool", "sword", True, False,
        definition={"onRightClicked": {"name": "DoThing"}},
    )
    assert e003_missing_procedure_hook(ws(elements=[hooked, proc])) == []


def test_e004():
    el = Element(
        "Ore", "block", "ore", True, False,
        definition={"texture": "shiny_ore"},
    )
    missing = e004_missing_texture(ws(elements=[el], texture_files=set()))
    assert len(missing) == 1
    assert missing[0].rule_id == "E004"
    assert "'shiny_ore.png'" in missing[0].message

    found = e004_missing_texture(
        ws(elements=[el], texture_files={"block/shiny_ore.png"})
    )
    assert found == []


def test_w001():
    findings = w001_duplicate_display_names(ws(language_map={"en_us": {
        "item.a": "Rune",
        "item.b": "Rune",
        "item.c": "Sword",
    }}))
    assert len(findings) == 1
    assert findings[0].rule_id == "W001"
    assert findings[0].element is None
    assert "2 different things" in findings[0].message
    assert "item.a" in findings[0].detail and "item.b" in findings[0].detail


def test_w002():
    unused = Element("LonelyProc", "procedure", "lonely", True, False)
    other = Element("ABlock", "block", "a_block", True, False)
    findings = w002_procedure_never_used(ws(elements=[unused, other]))
    assert len(findings) == 1
    assert findings[0].rule_id == "W002"

    used_by_hook = Element(
        "ABlock", "block", "a_block", True, False,
        definition={"onRightClicked": {"name": "LonelyProc"}},
    )
    assert w002_procedure_never_used(ws(elements=[unused, used_by_hook])) == []

    caller = Element(
        "Caller", "procedure", "caller", True, False,
        definition={"procedurexml": xml_with("LonelyProc")},
    )
    by_words = w002_procedure_never_used(ws(elements=[unused, caller]))
    assert [f.element for f in by_words] == ["Caller"]


def test_w003():
    proc = Element(
        "P", "procedure", "p", True, False,
        definition={"procedurexml": xml_with("usedVar")},
    )
    used = Variable("usedVar", "number", "map", "0")
    unused = Variable("ghostVar", "number", "map", "0")
    findings = w003_variable_never_used(ws(elements=[proc], variables=[used, unused]))
    assert len(findings) == 1
    assert "ghostVar" in findings[0].message

    # MCreator writes workspace vars as global:<name> in Blockly XML.
    mcreator_proc = Element(
        "P", "procedure", "p", True, False,
        definition={"procedurexml": xml_with("global:clickedRune")},
    )
    clicked = Variable("clickedRune", "number", "map", "0")
    assert w003_variable_never_used(
        ws(elements=[mcreator_proc], variables=[clicked])
    ) == []


def test_w004():
    named = Element("Ore", "block", "ore", True, False)
    unnamed = Element("Dust", "item", "dust", True, False)
    skip = Element("MyBiome", "biome", "my_biome", True, False)
    findings = w004_no_display_name(ws(
        elements=[named, unnamed, skip],
        language_map={"en_us": {"item.testmod.ore": "Ore"}},
    ))
    assert [f.element for f in findings] == ["Dust"]
    assert findings[0].rule_id == "W004"


def test_run_all_sort_and_exit_order():
    broken = Element("Zed", "block", "zed", compiles=False, locked_code=False)
    unnamed = Element("Amy", "item", "amy", True, False)
    findings = run_all(ws(elements=[broken, unnamed]))
    assert findings[0].severity == Severity.ERROR
    assert findings[0].element == "Zed"
    assert findings[1].severity == Severity.WARNING
    assert findings[1].element == "Amy"
    assert len(ALL_RULES) == 8


def test_load_any_zip_with_wrapper():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wrapped = tmp_path / "wrapper" / "MyMod"
        wrapped.mkdir(parents=True)
        (wrapped / ".mcreator").mkdir()  # cache dir must not be chosen
        (wrapped / "elements").mkdir()
        (wrapped / "MyMod.mcreator").write_text(json.dumps({
            "workspaceSettings": {"modid": "mymod", "modName": "My Mod"},
            "mod_elements": [],
            "variable_elements": [],
            "language_map": {"en_us": {}},
            "mcreatorVersion": 1,
        }), encoding="utf-8")

        zip_path = tmp_path / "export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for path in wrapped.rglob("*"):
                zf.write(path, path.relative_to(tmp_path))

        loaded = load_any(zip_path)
        assert loaded.mod_name == "My Mod"
        assert loaded.modid == "mymod"
        assert loaded.elements == []

        # Folder with a wrapper works too.
        loaded_dir = load_any(tmp_path / "wrapper")
        assert loaded_dir.modid == "mymod"


def test_cli_happy_and_error(monkey_ws_ok=True):
    import cli as cli_mod

    clean = ws()
    # Patch load_any via the already-imported name in cli.
    cli_mod.load_any = lambda path: clean
    sys.argv = ["cli.py", "dummy"]
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        code = cli_mod.main()
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert code == 0
    assert "No problems found" in out

    dirty = ws(elements=[
        Element("Bad", "block", "bad", compiles=False, locked_code=False),
    ])
    cli_mod.load_any = lambda path: dirty
    buf = io.StringIO()
    sys.stdout = buf
    try:
        code = cli_mod.main()
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert code == 1
    assert "ERRORS" in out
    assert "E001" in out


if __name__ == "__main__":
    tests = [
        test_e001, test_e002, test_e003, test_e004,
        test_w001, test_w002, test_w003, test_w004,
        test_run_all_sort_and_exit_order,
        test_load_any_zip_with_wrapper,
        test_cli_happy_and_error,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
