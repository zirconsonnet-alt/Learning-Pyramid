# Remove Legacy Default Material Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the product and data-model concept where a subject root doubles as a default study material.

**Architecture:** A subject remains the stable container project. Every study material, including the automatically created first course material, is a normal child project linked by `SubjectMaterialLink`. Existing legacy subjects are migrated by creating a child material project and moving the exposed material pointer away from the subject root before normal material operations run.

**Tech Stack:** FastAPI backend, in-memory domain store with SQLite/Postgres snapshot persistence, React frontend, pytest.

---

### Task 1: Regression Tests

**Files:**
- Modify: `tests/test_subjects_api.py`
- Modify: `tests/test_runtime_backup_restore.py`
- Modify: `tests/test_frontend_subject_project_copy.py`

- [ ] Add tests proving `POST /api/subjects` returns one material whose `projectId` differs from `subjectId`.
- [ ] Add tests proving deleting the first course material keeps the subject accessible and does not delete sibling material projects.
- [ ] Add a legacy snapshot restore test proving a `legacy_main` material whose `projectId == subjectId` is exposed as a migrated child project.
- [ ] Add static frontend copy checks banning `默认网课项目`, `默认项目`, and `legacy_main` from subject/project user-facing files.
- [ ] Run the focused tests and verify they fail before implementation.

### Task 2: Backend Semantics

**Files:**
- Modify: `backend/system/api.py`
- Modify: `adapter/routers/projects.py`

- [ ] Change `SystemAPI.create_subject()` so it creates the subject root, marks materials initialized, then creates the first course material via the normal child-project path.
- [ ] Remove synthetic `legacy_main` material fallback from `_list_subject_materials_from_store()`.
- [ ] Add a migration helper that replaces legacy root-backed materials with independent child projects before listing, resolving, editing, or deleting materials.
- [ ] Ensure hosted auth grants the creator ownership of both the subject root and the automatically created first child project.
- [ ] Keep subject deletion recursive: deleting a subject deletes all child material projects; deleting one material only deletes that material project.

### Task 3: Frontend And Docs Cleanup

**Files:**
- Modify: `frontend/src/views/guide/CreateSubjectProjectDemoPage.tsx`
- Modify: `docs/how-to-create-subject-project.md`
- Modify: `specs/010-retire-compatibility-project/spec.md`
- Modify: `specs/010-retire-compatibility-project/data-model.md`
- Modify: `specs/010-retire-compatibility-project/quickstart.md`
- Modify: `specs/010-retire-compatibility-project/tasks.md`

- [ ] Replace “默认网课项目/默认项目” copy with “第一个网课项目/普通项目”.
- [ ] Update old compatibility spec notes so they document migration away from root-backed materials instead of preserving them.
- [ ] Run frontend static tests that guard against copy regression.

### Task 4: Verification And Release

**Files:**
- No new files expected.

- [ ] Run focused backend and frontend-copy tests.
- [ ] Run the existing deploy/build command used by the repo if focused tests pass.
- [ ] Commit with a message naming the legacy default-material cleanup.
- [ ] Push the current branch and deploy the updated build.
