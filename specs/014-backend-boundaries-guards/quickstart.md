# Quickstart: Backend Boundaries and Guards

## Review the Boundary Design

1. Read `specs/014-backend-boundaries-guards/spec.md`.
2. Read `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md`.
3. Confirm each backend change under review has one owning boundary.

## Expected Verification Commands

Run after implementation:

```powershell
python tools/verify_backend_boundaries.py
python tools/verify_backend_boundaries.py --report-only
python -m unittest tests.test_backend_boundary_guards -v
python -m unittest tests.test_subject_material_atomicity tests.test_scoped_project_api_boundaries -v
python tools/verify_scoped_project_routes.py
python -m compileall -q backend adapter tests tools
rg -n "from __future__ import annotations" backend adapter tests tools
```

`python tools/verify_backend_boundaries.py` exits with code `1` when it reports boundary findings. Use `--report-only` when documenting existing risks without hiding them.

## Final Verification Notes

Results from 2026-05-10:

- `python -m unittest tests.test_backend_boundary_guards -v`: passed.
- `python -m unittest tests.test_subject_material_atomicity tests.test_scoped_project_api_boundaries -v`: passed.
- `python tools/verify_scoped_project_routes.py`: passed.
- `python tools/verify_backend_boundaries.py --report-only`: reported the documented current repository findings.
- `python tools/verify_backend_boundaries.py`: exited with code `1` because findings are present, matching the contract.
- `python -m compileall -q backend adapter tests tools`: passed; generated `__pycache__` directories under those roots were removed.
- `rg -n "from __future__ import annotations" backend adapter tests tools`: no matches.

## Review Checklist

- Router changes adapt requests/responses and do not own storage semantics.
- Scoped project routes use the approved scoped identity boundary.
- User ownership is subject-based.
- Cross-project lifecycle mutations use the approved atomic behavior owner.
- Migration behavior is documented as risk and not expanded.
