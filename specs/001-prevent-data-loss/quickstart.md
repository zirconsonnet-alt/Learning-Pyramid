# Quickstart: Prevent Server Data Loss

## 1. Run Current Safety Checks

```powershell
python -m pytest tests/test_hosted_deployment_checks.py -q
python -m pytest tests/test_data_safety_status.py -q
python -m pytest tests/test_runtime_backup_restore.py tests/test_data_safety_integrity.py tests/test_data_safety_audit.py -q
cd frontend && pnpm build
```

Expected result: deployment safety tests pass, including checks that self-host persistent project data is mounted correctly.

Implementation entry points:

- Domain/status models: `backend/system/data_safety.py`
- Audit helpers: `backend/system/data_safety_audit.py`
- Hosted preflight checks: `backend/system/hosted_deployment_checks.py`
- System API route: `adapter/routers/system.py`
- Frontend system API client: `frontend/src/ui/api/system.ts`

## 2. Create A Verified Backup With Media

```powershell
python tools/backup_runtime_bundle.py .\backups\runtime.zip --include-media --verify
```

Expected result: command exits `0`, writes a manifest, includes media payload files, and reports a verified backup.

## 3. Validate Restore Before Applying

```powershell
python tools/restore_runtime_bundle.py .\backups\runtime.zip --dry-run
```

Expected result: command prints what would be created or replaced and refuses to apply changes without explicit confirmation.

## 4. Check Broken Media Detection

Create a test media reference, remove only the referenced file in a disposable environment, then run:

```powershell
python tools/check_data_safety.py --json
```

Expected result: output contains a blocking `MEDIA_FILE_MISSING` finding with affected project and asset ids.

## 5. Verify Deployment Gate Behavior

Run the self-host sync workflow in a test environment with the protected `/app/data` mount intentionally missing.

Expected result: preflight exits non-zero before container replacement or file sync can affect production data.

## 6. Verify Post-Deploy Data Access

After a normal deploy, confirm that postflight validates representative users, projects, recall points, and media references.

Expected result: deployment is marked successful only when data-safety status is `ok` or contains only accepted warnings.

## 6a. Confirm Release Gate

```powershell
python tools/check_data_safety.py --json
```

Expected result before release: `releaseBlocked` is `false` and `findings` is empty or contains only accepted non-blocking warnings.

## 7. Frontend/API Behavior

When the backend reports `state=blocked` or `state=unknown`, the UI must show data unavailable/degraded state instead of an empty project workspace.

Expected result: users never see a silent empty state caused by inaccessible protected data.
