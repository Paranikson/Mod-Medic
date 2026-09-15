# Test fixtures

`working/` is a trimmed copy of `kgm_manual`. It should produce warnings (duplicate display names, unused procedures) but no ERROR findings.

`broken/` is the same workspace with three planted faults:

- `CustomWeapon.repairItems` points at `CUSTOM:IngotDeleted`
- `CustomWither.whenMobDies` points at `MissingProcedure`
- `textures/item/customsword.png` was renamed away

Regenerate with `python tools/make_fixture.py <source_workspace> <working|broken>`.
