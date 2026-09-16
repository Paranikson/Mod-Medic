# Test fixtures

`working/` is a trimmed copy of `kgm_manual`. It should produce warnings (duplicate display names, unused procedures) but no ERROR findings.

`broken/` is the same workspace with three planted faults:

- `CustomWeapon.repairItems` points at `CUSTOM:IngotDeleted`
- `CustomWither.whenMobDies` points at `MissingProcedure`
- `textures/item/customsword.png` was renamed away

Regenerate with `python tools/make_fixture.py <source_workspace> <working|broken>`.

## Running tests

```
pip install -r requirements-dev.txt
python -m pytest
```

## Running the API

```
pip install -r requirements.txt
uvicorn api:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API. `POST /api/validate` accepts a workspace `.zip`.
