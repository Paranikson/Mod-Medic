"""Rule checks against the committed working and broken workspace fixtures."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mcreator_model import load_any
from rules import ALL_RULES, Finding, Severity, run_all

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Rule ids this module asserts on. test_every_rule_is_registered fails if
# one of these is silently dropped from ALL_RULES.
REFERENCED_RULE_IDS = ("E002", "E003", "E004", "W001")


@pytest.fixture(scope="module")
def working_ws():
    return load_any(FIXTURES / "working")


@pytest.fixture(scope="module")
def broken_ws():
    return load_any(FIXTURES / "broken")


@pytest.fixture(scope="module")
def working_findings(working_ws):
    return run_all(working_ws)


@pytest.fixture(scope="module")
def broken_findings(broken_ws):
    return run_all(broken_ws)


def _errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == Severity.ERROR]


def _mentions(finding: Finding, needle: str) -> bool:
    return needle in finding.message or needle in finding.detail


def _w001_key_counts(findings: list[Finding]) -> list[int]:
    counts = []
    for finding in findings:
        if finding.rule_id != "W001":
            continue
        keys = [k.strip() for k in finding.detail.split(",") if k.strip()]
        counts.append(len(keys))
    return counts


def test_working_has_no_errors(working_findings):
    assert _errors(working_findings) == []


def test_broken_has_exactly_three_errors(broken_findings):
    assert len(_errors(broken_findings)) == 3


def test_broken_missing_reference(broken_findings):
    assert any(
        f.rule_id == "E002"
        and f.element == "CustomWeapon"
        and _mentions(f, "IngotDeleted")
        for f in broken_findings
    )


def test_broken_missing_procedure(broken_findings):
    assert any(
        f.rule_id == "E003"
        and f.element == "CustomWither"
        and _mentions(f, "MissingProcedure")
        for f in broken_findings
    )


def test_broken_missing_texture(broken_findings):
    assert any(
        f.rule_id == "E004"
        and f.element == "CustomWeapon"
        and _mentions(f, "customsword")
        for f in broken_findings
    )


def test_duplicate_display_names(working_findings, broken_findings):
    assert 7 in _w001_key_counts(working_findings)
    assert 7 in _w001_key_counts(broken_findings)


def test_every_rule_is_registered():
    registered = {
        rule.__name__.split("_", 1)[0].upper()
        for rule in ALL_RULES
    }
    missing = set(REFERENCED_RULE_IDS) - registered
    assert missing == set(), f"dropped from ALL_RULES: {sorted(missing)}"


def test_zip_and_folder_agree(tmp_path):
    folder = FIXTURES / "working"
    zip_path = tmp_path / "working.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder))

    from_zip = run_all(load_any(zip_path))
    from_folder = run_all(load_any(folder))
    assert from_zip == from_folder
