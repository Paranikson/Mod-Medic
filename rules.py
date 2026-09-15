#!/usr/bin/env python3
"""
Checks that look at a loaded MCreator workspace and report problems.

Each rule is a function: Workspace -> list[Finding]. Add a new rule by
writing the function and appending it to ALL_RULES. Nothing else needs
to change.

Messages are written for instructors and 11-13 year old students.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from mcreator_model import Workspace


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    element: str | None  # element name, or None if workspace-level
    message: str         # plain language, addressed to the student
    detail: str = ""     # optional technical specifics


Rule = Callable[[Workspace], list[Finding]]

# Sort ERROR before WARNING before INFO. Enum value strings would not.
_SEVERITY_ORDER = {
    Severity.ERROR: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


def e001_element_does_not_compile(ws: Workspace) -> list[Finding]:
    """E001 - the element is marked as not compiling in the workspace index."""
    findings: list[Finding] = []
    for el in ws.elements:
        if el.compiles is False:
            findings.append(Finding(
                rule_id="E001",
                severity=Severity.ERROR,
                element=el.name,
                message=(
                    f"{el.name} has an error inside it. Open it in MCreator "
                    "and look for red warnings."
                ),
            ))
    return findings


def e002_missing_element_ref(ws: Workspace) -> list[Finding]:
    """E002 - a CUSTOM: pointer names an element that is not in this workspace."""
    findings: list[Finding] = []
    for el in ws.elements:
        for ref in el.refs():
            if ref.kind == "custom" and ref.target not in ws.element_names:
                findings.append(Finding(
                    rule_id="E002",
                    severity=Severity.ERROR,
                    element=el.name,
                    message=(
                        f"{el.name} points at '{ref.target}', but nothing in "
                        "this workspace is called that. It was probably "
                        "renamed or deleted."
                    ),
                ))
    return findings


def e003_missing_procedure_hook(ws: Workspace) -> list[Finding]:
    """E003 - a procedure hook names a procedure that does not exist."""
    findings: list[Finding] = []
    for el in ws.elements:
        for ref in el.refs():
            if ref.kind == "procedure" and ref.target not in ws.element_names:
                findings.append(Finding(
                    rule_id="E003",
                    severity=Severity.ERROR,
                    element=el.name,
                    message=(
                        f"{el.name} is set to run the procedure '{ref.target}', "
                        "but that procedure doesn't exist."
                    ),
                ))
    return findings


def e004_missing_texture(ws: Workspace) -> list[Finding]:
    """E004 - an element names a texture file that is not on disk."""
    findings: list[Finding] = []
    for el in ws.elements:
        for _field, value in el.textures():
            if not ws.has_texture(el.type, value):
                findings.append(Finding(
                    rule_id="E004",
                    severity=Severity.ERROR,
                    element=el.name,
                    message=(
                        f"{el.name} is looking for a texture called "
                        f"'{value}.png', but that image isn't in the workspace."
                    ),
                ))
    return findings


def w001_duplicate_display_names(ws: Workspace) -> list[Finding]:
    """W001 - two or more translation keys share the same English display name."""
    findings: list[Finding] = []
    en_us = ws.language_map.get("en_us", {})
    by_label: dict[str, list[str]] = defaultdict(list)
    for key, label in en_us.items():
        by_label[label].append(key)
    for label, keys in by_label.items():
        if len(keys) >= 2:
            findings.append(Finding(
                rule_id="W001",
                severity=Severity.WARNING,
                element=None,
                message=(
                    f"{len(keys)} different things are all named '{label}' "
                    "in the game. Players won't be able to tell them apart."
                ),
                detail=", ".join(keys),
            ))
    return findings


def w002_procedure_never_used(ws: Workspace) -> list[Finding]:
    """
    W002 - a procedure is never attached to anything and never called.

    It counts as used if some *other* element either has a procedure-hook
    pointing at it, or mentions its name in Blockly XML.
    """
    findings: list[Finding] = []
    for el in ws.elements:
        if el.type != "procedure":
            continue
        used = False
        for other in ws.elements:
            if other.name == el.name:
                continue
            if any(
                ref.kind == "procedure" and ref.target == el.name
                for ref in other.refs()
            ):
                used = True
                break
            if el.name in other.words_used():
                used = True
                break
        if not used:
            findings.append(Finding(
                rule_id="W002",
                severity=Severity.WARNING,
                element=el.name,
                message=(
                    f"The procedure {el.name} was built, but nothing ever "
                    "runs it. Check that you attached it to a block, item "
                    "or entity."
                ),
            ))
    return findings


def _variable_mentioned(name: str, words: set[str]) -> bool:
    """True if Blockly XML mentions this workspace variable.

    MCreator stores references as 'global:clickedRune' (or 'player:...'),
    not the bare name. The bare name still counts, so tests and older
    workspaces keep working.
    """
    if name in words:
        return True
    return any(word.endswith(":" + name) for word in words)


def w003_variable_never_used(ws: Workspace) -> list[Finding]:
    """W003 - a workspace variable never appears in any element's Blockly XML."""
    findings: list[Finding] = []
    words: set[str] = set()
    for el in ws.elements:
        words |= el.words_used()
    for var in ws.variables:
        if not _variable_mentioned(var.name, words):
            findings.append(Finding(
                rule_id="W003",
                severity=Severity.WARNING,
                element=None,
                message=(
                    f"The variable {var.name} was created, but no procedure "
                    "uses it."
                ),
            ))
    return findings


def w004_no_display_name(ws: Workspace) -> list[Finding]:
    """
    W004 - a visible in-game element has no English translation key.

    Keys look like item.modid.registry_name, so matching the suffix
    "." + registry_name covers blocks, items, tools, and entities.
    """
    findings: list[Finding] = []
    en_us = ws.language_map.get("en_us", {})
    named_types = ("block", "item", "tool", "livingentity")
    for el in ws.elements:
        if el.type not in named_types:
            continue
        suffix = "." + el.registry_name
        if not any(key.endswith(suffix) for key in en_us):
            findings.append(Finding(
                rule_id="W004",
                severity=Severity.WARNING,
                element=el.name,
                message=(
                    f"{el.name} has no display name, so it will show up "
                    "with a broken name in the game."
                ),
            ))
    return findings


ALL_RULES: list[Rule] = [
    e001_element_does_not_compile,
    e002_missing_element_ref,
    e003_missing_procedure_hook,
    e004_missing_texture,
    w001_duplicate_display_names,
    w002_procedure_never_used,
    w003_variable_never_used,
    w004_no_display_name,
]


def run_all(ws: Workspace) -> list[Finding]:
    """Run every registered rule and sort findings by severity, then name."""
    findings: list[Finding] = []
    for rule in ALL_RULES:
        findings.extend(rule(ws))
    findings.sort(key=lambda f: (
        _SEVERITY_ORDER[f.severity],
        f.element or "",
    ))
    return findings
