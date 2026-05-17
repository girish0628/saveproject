# SaveProject — Project Context

## What this is
ArcGIS Python Toolbox (`.pyt`) exposing a 5-operation CRUD API over a single
File Geodatabase feature class (`PROJECTS`). Consumed by Experience Builder
widgets via a secured ArcGIS GP Service.

---

## Folder structure

```
SaveProject.pyt          ← ArcGIS toolbox entry point
project_api/             ← one file per GP tool (no subfolders)
    __init__.py
    create_project.py    ← POST   /api/projects
    delete_project.py    ← DELETE /api/projects/{id}
    get_all_projects.py  ← GET    /api/projects
    get_project_by_id.py ← GET    /api/projects/{id}
    update_project.py    ← PUT    /api/projects/{id}
helpers/                 ← all supporting code (no subfolders)
    __init__.py
    constants.py         ← every constant: field names, cursor lists, lengths, messages, log settings
    project_model.py     ← Project dataclass + from_row() + to_dict()
    project_service.py   ← ProjectValidator + ProjectService (all business logic)
    utils.py             ← ResponseModel + get_logger/ArcPyMessageHandler + ArcPy cursor helpers
DATA/
    SavedProject.gdb/
        PROJECTS         ← the only feature class; pre-exists, never created by code
logs/
    project_api.log      ← rotating log file (5 MB × 3 backups)
```

---

## PROJECTS feature class schema

| Field | Type | Length | Notes |
|---|---|---|---|
| OBJECTID | OID | — | DB-managed |
| PROJECT_ID | Text | 255 | UUID, app-generated |
| NAME | Text | 255 | Required |
| DESCRIPTION | Text | 1000 | Optional |
| WEBMAP_ID | Text | 255 | Required |
| EXTENT | Text | 255 | JSON: `{"xmin","xmax","ymin","ymax"}` |
| MAP_STATE | Text | 4000 | JSON array |
| GRAPHICS | Text | 4000 | GeoJSON array |
| PERMISSIONS | Text | 4000 | `"email:ROLE,email:ROLE"` (EDIT or VIEW) |
| THUMBNAIL | **BLOB** | — | Raw binary; Base64 encoded/decoded at API boundary |
| SHARED | SmallInteger | — | 0 = private, 1 = public |
| OWNER | Text | 255 | Always set from userEmail — never from payload |
| GlobalID | GlobalID | — | DB-managed |
| created_user | Text | 255 | Editor tracking (field name is `created_user`) |
| created_date | Date | — | Editor tracking (field name is `created_date`, NOT `create_date`) |
| last_edited_user | Text | 255 | Editor tracking |
| last_edited_date | Date | — | Editor tracking |

> **Important:** The feature class is a polygon FC (has Shape, Shape_Length, Shape_Area).
> Inserts via `InsertCursor` without `SHAPE@` create null-geometry rows — acceptable for
> metadata-only storage.

---

## Architecture rules

- **No dynamic schema.** The FGDB and PROJECTS feature class pre-exist. The code never
  creates tables or fields.
- **Owner-only writes.** Only the project OWNER may update or delete. Shared users are
  read-only.
- **OWNER is always forced.** `data[FIELD_OWNER]` is overwritten with `userEmail` in the
  service — the payload value is never trusted.
- **PROJECT_ID is auto-generated.** UUID4, uppercase, no dashes. Never supplied by the caller.
- **PERMISSIONS is a denormalised string.** Format: `"email:ROLE,email:ROLE"`.
  Access filtering is done in Python (not SQL) to avoid partial LIKE mis-fires.

---

## Security model

The GP Service is secured via Portal sharing/groups — no token logic in Python.
`userEmail` is a **Required** `GPString` parameter on every tool, populated by
Experience Builder from the authenticated Portal session before the tool runs.
Python trusts this value as the authenticated principal.

---

## Exception → HTTP status mapping

| Exception | Status |
|---|---|
| `PermissionError` | 403 |
| `LookupError` | 404 |
| `ValueError` | 400 |
| `FileNotFoundError` | 500 |
| `RuntimeError` | 500 |
| anything else | 500 |

No custom exception classes. Standard Python exceptions only.

---

## THUMBNAIL — BLOB handling

- **DB storage:** raw `bytearray` written to a BLOB field.
- **API boundary:** Base64 string in GP parameters and JSON responses.
- **Write path:** `_b64_to_blob(b64_str)` in `project_service.py` decodes Base64 → `bytearray`.
- **Read path:** `_blob_to_b64(blob_val)` in `project_model.py` converts ArcPy
  `memoryview`/`bytearray` → Base64 string.
- To migrate an existing TEXT THUMBNAIL field to BLOB:
  ```python
  import arcpy
  fc = r"DATA\SavedProject.gdb\PROJECTS"
  arcpy.management.DeleteField(fc, "THUMBNAIL")
  arcpy.management.AddField(fc, "THUMBNAIL", "BLOB")
  ```

---

## Module cache eviction

`SaveProject.pyt` evicts all cached `project_api.*` and `helpers.*` modules on every
toolbox refresh so ArcGIS Pro always loads fresh source:

```python
_stale = [k for k in sys.modules if k.startswith(("project_api", "helpers"))]
for _mod in _stale:
    del sys.modules[_mod]
```

If stale `.pyc` bytecode persists, delete all `__pycache__` folders:
```powershell
Get-ChildItem -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force
```

---

## Key import paths

```python
from helpers.constants       import FIELD_NAME, FC_PROJECTS, ...
from helpers.project_model   import Project
from helpers.project_service import ProjectService
from helpers.utils           import get_logger, ResponseModel, fetch_one, ...
```

All `project_api/*.py` tools add the project root to `sys.path` via:
```python
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
```

---

## ResponseModel shape

```json
{
  "success":     true | false,
  "message":     "Human-readable status",
  "data":        { ... } | [ ... ] | null,
  "status_code": 200 | 201 | 400 | 403 | 404 | 500
}
```

Every tool writes this JSON to the GP messages pane via `arcpy.AddMessage` (success)
or `arcpy.AddError` (failure).

---

## Coding conventions

- No custom exception classes — use `ValueError`, `LookupError`, `PermissionError`,
  `FileNotFoundError`, `RuntimeError`.
- No docstrings on individual methods unless the why is non-obvious.
- No feature flags, no backwards-compatibility shims.
- Validate at the API boundary (`project_service.py → ProjectValidator`); trust internal
  code.
- `_get_str(parameters, index)` in every tool strips whitespace and returns `""` on
  missing/null — never raises.
- Log settings live in `helpers/constants.py` (`LOG_DIR`, `LOG_FILE`, `LOG_LEVEL`).
  Default level is `DEBUG`; override with the `LOG_LEVEL` env variable.
