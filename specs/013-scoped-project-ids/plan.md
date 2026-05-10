# Scoped Project IDs Implementation Plan

## Boundary

Feature 013 keeps subject-scoped project ids as the public API identity and keeps internal project keys as storage-only implementation details.

Affected paths:
- `adapter/scoped_projects.py`
- `adapter/routers/projects.py`
- `adapter/routers/system.py`
- `adapter/routers/asr.py`
- `adapter/routers/media.py`
- `backend/system/api.py`
- `tests/test_subject_material_atomicity.py`
- `tests/test_scoped_project_api_boundaries.py`

## Confirmed Decisions

1. Subject material mutations must be atomic across subject material records, child project state, scoped bindings, and generated id counters.
2. Upload endpoints must reject oversized requests before reading the full body when `Content-Length` is present.
3. ASR audio upload keeps `MAX_ASR_UPLOAD_BYTES`.
4. Image upload uses a 10 MB limit.
5. Scoped raw LLM chat is not a project-context endpoint. It must not silently behave like project LLM ask.
6. Auth ownership is stored on subject ids only. Internal material project keys must not be written into user ownership as a compatibility shortcut.

## Verification Commands

Run after changes:

```powershell
python -m unittest tests.test_subject_material_atomicity tests.test_scoped_project_api_boundaries -v
python -m compileall -q backend adapter tests tools
python tools/verify_scoped_project_routes.py
```

`tools/verify_scoped_project_ids.py` requires an existing report JSON passed with `--report`; it is not a standalone generator.
