# Quickstart: Retire Compatibility Project Validation

## Targeted Backend Tests

Run the subject/material contract regression suite:

```powershell
python -m pytest tests/test_subjects_api.py -q
```

Run persistence safety coverage if the implementation touches serialized project payloads:

```powershell
python -m pytest tests/test_sqlite_store.py tests/test_runtime_backup_restore.py -q
```

## Targeted Frontend And Static Tests

Run focused subject/project frontend regressions:

```powershell
python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_llm_settings_location.py tests/test_frontend_subject_project_copy.py tests/test_frontend_project_settings_layout.py -q
```

Run lint from `frontend/`:

```powershell
npx eslint src/ui/api/subjects.ts src/shell/AppShell.tsx src/views/projects/ProjectsPage.tsx src/views/subjects/SubjectDashboardPage.tsx src/views/settings/ProjectSettingsPage.tsx src/views/pomodoro/PomodoroPage.tsx src/views/pomodoro/PomodoroWorkbenchGate.tsx
```

Run the frontend build from `frontend/`:

```powershell
npm run build
```

## Manual Validation Scenario

1. Create a subject.
2. Confirm the subject opens in the subject dashboard and still routes into subject-level settings correctly.
3. Confirm the subject has an automatically created first material project whose project id is different from the subject root id.
4. Open the material project workbench and project settings.
5. Confirm Pomodoro project selection offers only real material projects, not the subject root.
6. Delete a material project and confirm the subject remains.
7. Delete the subject and confirm all related project entries are removed together.
8. Re-open historical data or a saved runtime snapshot created before the refactor and confirm the subject and material routes still resolve.

## Expected Checks

- Current subject contracts expose `subjectProjectId` and not `compatibilityProjectId`.
- Current material contracts expose `projectId` and not `compatibilityProjectId`.
- Historical records using the retired field names remain readable, and historical root-backed materials are migrated to independent material projects.
- AppShell, settings, and Pomodoro still distinguish subject-root scope from material-project scope correctly.
- User-facing docs no longer describe a compatibility-project concept.
- User-facing docs no longer describe a default-project concept.

## Latest Validation Notes

- `python -m pytest tests/test_subjects_api.py tests/test_frontend_llm_settings_location.py -q` passed on 2026-05-06.
- `python -m pytest tests/test_subjects_api.py tests/test_runtime_backup_restore.py -q` passed on 2026-05-06.
- `python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_project_settings_layout.py tests/test_frontend_subject_project_copy.py tests/test_spec_alignment.py -q` passed on 2026-05-06.
