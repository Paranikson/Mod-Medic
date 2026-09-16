#!/usr/bin/env python3
"""
HTTP API for Mod Medic. Wraps load_any() and run_all(); does not persist uploads.

    uvicorn api:app --reload
"""

from __future__ import annotations

import inspect
import os
import tempfile
import zipfile
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mcreator_model import load_any
from rules import ALL_RULES, Finding, Severity, run_all

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SeverityName = Literal["error", "warning", "info"]

app = FastAPI(title="Mod Medic", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FindingOut(BaseModel):
    rule_id: str
    severity: SeverityName
    element: str | None
    message: str
    detail: str = ""


class CountsOut(BaseModel):
    error: int
    warning: int
    info: int


class ValidateOut(BaseModel):
    mod_name: str
    element_count: int
    variable_count: int
    texture_count: int
    findings: list[FindingOut]
    counts: CountsOut


class RuleOut(BaseModel):
    rule_id: str
    severity: SeverityName
    description: str


class HealthOut(BaseModel):
    status: str


def _finding_out(finding: Finding) -> FindingOut:
    return FindingOut(
        rule_id=finding.rule_id,
        severity=finding.severity.value,
        element=finding.element,
        message=finding.message,
        detail=finding.detail,
    )


def _counts(findings: list[Finding]) -> CountsOut:
    return CountsOut(
        error=sum(1 for f in findings if f.severity == Severity.ERROR),
        warning=sum(1 for f in findings if f.severity == Severity.WARNING),
        info=sum(1 for f in findings if f.severity == Severity.INFO),
    )


def _rule_id(rule) -> str:
    return rule.__name__.split("_", 1)[0].upper()


def _rules_catalog() -> list[RuleOut]:
    """Describe ALL_RULES without running them, so the OpenAPI list stays in sync."""
    catalog: list[RuleOut] = []
    for rule in ALL_RULES:
        rule_id = _rule_id(rule)
        severity: SeverityName = {
            "E": "error",
            "W": "warning",
            "I": "info",
        }[rule_id[0]]
        first = (inspect.getdoc(rule) or "").split("\n", 1)[0].strip()
        prefix = f"{rule_id} - "
        if first.lower().startswith(prefix.lower()):
            first = first[len(prefix):]
        catalog.append(RuleOut(rule_id=rule_id, severity=severity, description=first))
    return catalog


def _unlink(path: str | None) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@app.get("/api/rules", response_model=list[RuleOut])
def list_rules() -> list[RuleOut]:
    return _rules_catalog()


@app.post("/api/validate", response_model=ValidateOut)
async def validate(file: UploadFile = File(...)) -> ValidateOut:
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload a .zip file. In MCreator, use File then "
                "Export workspace to ZIP, and upload that."
            ),
        )

    tmp_path: str | None = None
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            prefix="modmedic_upload_",
            suffix=".zip",
            delete=False,
        )
        tmp_path = handle.name
        size = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="That file is too big. Workspace zips must be under 50 MB.",
                )
            handle.write(chunk)
        handle.close()
        handle = None

        try:
            ws = load_any(tmp_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=422,
                detail=(
                    "I couldn't find an MCreator workspace in that zip. "
                    "If you zipped the folder yourself, make sure the "
                    "workspace is inside it."
                ),
            ) from None
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail=(
                    "That .zip file could not be opened. "
                    "Try exporting it from MCreator again."
                ),
            ) from None

        findings = run_all(ws)
        return ValidateOut(
            mod_name=ws.mod_name or ws.modid or "",
            element_count=len(ws.elements),
            variable_count=len(ws.variables),
            texture_count=len(ws.texture_files),
            findings=[_finding_out(f) for f in findings],
            counts=_counts(findings),
        )
    finally:
        if handle is not None:
            handle.close()
        _unlink(tmp_path)
        await file.close()
