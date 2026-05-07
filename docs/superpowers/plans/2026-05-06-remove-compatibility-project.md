# Remove Compatibility Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `compatibilityProjectId` / `compatibility_project_id` as a product, API, and frontend concept while keeping existing subject and material data readable.

**Architecture:** Treat `subject -> material -> project/workbench` as the explicit model. A subject may still have a root project anchor for existing settings/statistics routes, but it is named `subjectProjectId`; a study material points to its workbench project with `projectId`. Persisted old data may still read `compatibilityProjectId`, but new DTOs and new persisted records must not emit it.

**Tech Stack:** Python/FastAPI adapter, backend domain models, JSON/SQLite/Postgres persistence payloads, React + TypeScript + zod frontend, pytest static/frontend tests, eslint, Vite build.

---

## Scope And Rules

- This is a cross-module refactor, not a point fix.
- Do not delete project data. The cleanup is about the dirty field/concept name and routing semantics.
- Keep backward read compatibility for old persisted records that contain `compatibilityProjectId`.
- Remove outbound API fields named `compatibilityProjectId`.
- Remove frontend references to `compatibilityProjectId` after the backend contract changes.
- Avoid changing unrelated project/workbench behavior.
- Current worktree already contains the Pomodoro stopgap edits. Review and preserve those changes while applying this refactor.

## Target Contract

### Subject DTO

```ts
type Subject = {
  subjectId: string
  subjectProjectId: string
  title: string
  state: string
  createdAt: string
  deletedAt: string | null
}
```

### Create Subject Result

```ts
type CreateSubjectResult = {
  subjectId: string
  subjectProjectId: string
}
```

### Study Material DTO

```ts
type StudyMaterial = {
  subjectId: string
  materialId: string
  materialType: "COURSE" | "BOOK" | "LOOSE_POINTS"
  title: string
  createdAt: string
  projectId: string | null
}
```

### Subject Context DTO

```ts
type SubjectContext = {
  subject: Subject
  currentMaterial: StudyMaterial
  materials: StudyMaterial[]
  isSubjectRoot: boolean
  currentProjectId: string
  subjectProjectId: string
}
```

## File Map

- Modify `backend/models/study_material.py`: rename internal field to `project_id`.
- Modify `backend/system/persistence_json.py`: write `projectId`, read `projectId` with fallback to old `compatibilityProjectId`.
- Modify `backend/system/api.py`: replace compatibility terminology in material creation, lookup, cleanup, edit/delete, and book initialization.
- Modify `adapter/mappers.py`: emit `subjectProjectId` and material `projectId`.
- Modify `adapter/routers/projects.py`: return `subjectProjectId`, use `item.project_id` for auth membership cleanup.
- Modify `frontend/src/ui/api/subjects.ts`: zod schemas and TS types for the new contract.
- Modify `frontend/src/views/projects/ProjectsPage.tsx`: use `subject.subjectProjectId`.
- Modify `frontend/src/views/subjects/SubjectDashboardPage.tsx`: use `material.projectId` and `subject.subjectProjectId`.
- Modify `frontend/src/shell/AppShell.tsx`: resolve subject and project context through clean fields.
- Modify `frontend/src/views/settings/ProjectSettingsPage.tsx`: use `material.projectId` for source material, deletion, and cleanup state.
- Modify `frontend/src/views/pomodoro/PomodoroPage.tsx`: filter subject root projects by `subject.subjectProjectId`.
- Modify `frontend/src/views/pomodoro/PomodoroWorkbenchGate.tsx`: same Pomodoro gate filter.
- Modify `tests/test_subjects_api.py`: update API contract tests and add negative assertions for removed fields.
- Modify `tests/test_frontend_llm_settings_location.py` or add a focused static test: assert frontend no longer references `compatibilityProjectId`.
- Modify `docs/learningpyramid-user-manual.md` and `docs/how-to-create-subject-project.md` only if wording mentions compatible/compatibility project behavior.

---

### Task 1: Lock The New API Contract In Tests

**Files:**
- Modify: `tests/test_subjects_api.py`
- Modify or add: `tests/test_frontend_llm_settings_location.py`

- [ ] **Step 1: Update subject create/list assertions**

In `tests/test_subjects_api.py`, update the create subject assertions from:

```python
assert create_data["compatibilityProjectId"] == subject_id
```

to:

```python
assert create_data["subjectProjectId"] == subject_id
assert "compatibilityProjectId" not in create_data
```

Update the expected subject DTO from:

```python
"compatibilityProjectId": subject_id,
```

to:

```python
"subjectProjectId": subject_id,
```

Add:

```python
assert "compatibilityProjectId" not in subjects[0]
```

- [ ] **Step 2: Update material assertions**

Replace every API test read of `material["compatibilityProjectId"]` with `material["projectId"]`.

For the default course material, assert:

```python
assert materials[0]["projectId"] == subject_id
assert "compatibilityProjectId" not in materials[0]
```

For newly created materials, use:

```python
book_project_id = book_material["projectId"]
assert book_project_id
assert book_project_id != subject_id
assert "compatibilityProjectId" not in book_material
```

- [ ] **Step 3: Add frontend/static guard**

Add or update a static assertion so future code does not reintroduce the dirty field:

```python
def test_frontend_subject_project_contract_no_compatibility_project_id() -> None:
    root = Path(__file__).resolve().parents[1]
    frontend_sources = [
        root / "frontend" / "src" / "ui" / "api" / "subjects.ts",
        root / "frontend" / "src" / "shell" / "AppShell.tsx",
        root / "frontend" / "src" / "views" / "projects" / "ProjectsPage.tsx",
        root / "frontend" / "src" / "views" / "subjects" / "SubjectDashboardPage.tsx",
        root / "frontend" / "src" / "views" / "settings" / "ProjectSettingsPage.tsx",
        root / "frontend" / "src" / "views" / "pomodoro" / "PomodoroPage.tsx",
        root / "frontend" / "src" / "views" / "pomodoro" / "PomodoroWorkbenchGate.tsx",
    ]
    for source_path in frontend_sources:
        assert "compatibilityProjectId" not in source_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run contract tests and verify they fail before implementation**

Run:

```bash
python -m pytest tests/test_subjects_api.py tests/test_frontend_llm_settings_location.py -q
```

Expected before implementation: failures mentioning missing `subjectProjectId` or `projectId`, and existing `compatibilityProjectId`.

---

### Task 2: Rename Backend Material Field And Persistence Payload

**Files:**
- Modify: `backend/models/study_material.py`
- Modify: `backend/system/persistence_json.py`
- Modify: `backend/system/api.py`

- [ ] **Step 1: Rename the domain field**

Change:

```python
compatibility_project_id: ProjectId | None = None
```

to:

```python
project_id: ProjectId | None = None
```

- [ ] **Step 2: Update JSON persistence write/read**

In `_encode_study_material`, write:

```python
"projectId": None if item.project_id is None else str(item.project_id),
```

In `_decode_study_material`, read new data first and old data second:

```python
raw_project_id = data.get("projectId", data.get("compatibilityProjectId"))
...
project_id=None if raw_project_id is None else ProjectId(str(raw_project_id)),
```

This keeps old local/backed-up records readable without continuing to write the old key.

- [ ] **Step 3: Update `SystemAPI` material construction**

Replace `compatibility_project_id=` with `project_id=` in:

- `_list_subject_materials_from_store`
- `create_subject`
- `create_subject_material`
- `edit_project` material sync

Rename local variables named `compatibility_project_id` to `material_project_id`.

- [ ] **Step 4: Update `SystemAPI` behavior reads**

Replace reads of `material.compatibility_project_id` with `material.project_id` in:

- `_resolve_current_material_for_project`
- `edit_subject_material`
- `delete_subject_material`
- `list_membership_cleanup_project_ids`
- `delete_project`
- `initialize_book_learning_objects_from_subject_material`

Historical note from the original plan:

```python
if material_project_id is None or id_canonical_text(material_project_id) == id_canonical_text(resolved_subject_id):
    raise PreconditionFailure("retired guard")
```

This guard has since been retired. Subject project cards are product-equal and can all be deleted while the subject remains.

- [ ] **Step 5: Rename helper**

Rename `_compatibility_project_options_for_material_type` to `_project_options_for_material_type`.

- [ ] **Step 6: Run backend tests and expect mapper/router failures**

Run:

```bash
python -m pytest tests/test_subjects_api.py -q
```

Expected at this point: failures in API DTOs or router code until Task 3 is complete.

---

### Task 3: Replace Outbound Adapter API Fields

**Files:**
- Modify: `adapter/mappers.py`
- Modify: `adapter/routers/projects.py`

- [ ] **Step 1: Update `subject_to_dto`**

Return:

```python
return {
    "subjectId": str(p.project_id),
    "subjectProjectId": str(p.project_id),
    "title": p.title,
    "state": _jsonable(p.state),
    "createdAt": _jsonable(p.created_at),
    "deletedAt": _jsonable(p.deleted_at),
}
```

- [ ] **Step 2: Update `study_material_to_dto`**

Return:

```python
"projectId": None if m.project_id is None else str(m.project_id),
```

and remove `compatibilityProjectId`.

- [ ] **Step 3: Update create subject route result**

Change:

```python
return {"ok": True, "data": {"subjectId": str(pid), "compatibilityProjectId": str(pid)}}
```

to:

```python
return {"ok": True, "data": {"subjectId": str(pid), "subjectProjectId": str(pid)}}
```

- [ ] **Step 4: Update auth cleanup for material projects**

Replace `item.compatibility_project_id` with `item.project_id` in create/delete material routes.

- [ ] **Step 5: Run backend contract tests**

Run:

```bash
python -m pytest tests/test_subjects_api.py -q
```

Expected after Task 3: subject API tests pass.

---

### Task 4: Move Frontend To Clean Subject/Material Fields

**Files:**
- Modify: `frontend/src/ui/api/subjects.ts`
- Modify: `frontend/src/views/projects/ProjectsPage.tsx`
- Modify: `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- Modify: `frontend/src/shell/AppShell.tsx`
- Modify: `frontend/src/views/settings/ProjectSettingsPage.tsx`
- Modify: `frontend/src/views/pomodoro/PomodoroPage.tsx`
- Modify: `frontend/src/views/pomodoro/PomodoroWorkbenchGate.tsx`

- [ ] **Step 1: Update zod schemas**

Use:

```ts
export const SubjectSchema = z.object({
  subjectId: z.string(),
  subjectProjectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})

export const StudyMaterialSchema = z.object({
  subjectId: z.string(),
  materialId: z.string(),
  materialType: StudyMaterialTypeSchema,
  title: z.string(),
  createdAt: z.string(),
  projectId: z.string().nullable(),
})

const CreateSubjectResultSchema = z.object({
  subjectId: z.string(),
  subjectProjectId: z.string(),
})
```

- [ ] **Step 2: Update `ProjectsPage`**

Replace:

```ts
subject.compatibilityProjectId
res.compatibilityProjectId
```

with:

```ts
subject.subjectProjectId
res.subjectProjectId
```

Use `subject.subjectProjectId` for audit log query and selected project state. Keep `/subjects/${subject.subjectId}` for entering the subject dashboard.

- [ ] **Step 3: Update `SubjectDashboardPage`**

Use:

```ts
const subject = (subjectsQ.data ?? []).find((item) => item.subjectId === subjectId) ?? null
const subjectProjectId = subject?.subjectProjectId ?? subjectId
```

Replace each `material.compatibilityProjectId` with `material.projectId`.

Keep behavior:

```ts
const projectId = material.projectId
if (!projectId) return
```

- [ ] **Step 4: Update `AppShell`**

Use `subject.subjectProjectId` for subject root project resolution:

```ts
const routeScopedProjectId = routeSubjectId ? routeSubject?.subjectProjectId ?? "" : ""
const resolvedSubjectProjectId = subjectContextQ.data?.subjectProjectId ?? routeSubject?.subjectProjectId ?? ""
const currentMaterialProjectId =
  subjectContextQ.data?.currentMaterial.projectId ?? (!isSubjectRoot ? currentProjectContextId : "")
```

Build the Pomodoro subject root set from:

```ts
new Set((allSubjectsQ.data ?? []).map((subject) => subject.subjectProjectId).filter(Boolean))
```

- [ ] **Step 5: Update settings page**

Replace material project reads with `projectId`:

```ts
const sourceCourseMaterials = subjectMaterials.filter(
  (material) => material.materialType === "COURSE" && material.projectId && material.projectId !== pid,
)

const canDeleteCurrentMaterial =
  !isSubjectSettingsScope &&
  currentMaterial !== null &&
  currentMaterial.projectId !== null &&
  currentMaterial.projectId !== subjectProjectId
```

Update cleanup:

```ts
const relatedProjectIds = [subjectProjectId, ...subjectMaterials.map((material) => material.projectId ?? "")]
```

- [ ] **Step 6: Update Pomodoro filters**

In both Pomodoro files, build the subject-root project id set from `subject.subjectProjectId`.

- [ ] **Step 7: Verify no frontend dirty field remains**

Run:

```bash
rg -n "compatibilityProjectId" frontend/src
```

Expected: no matches.

Run:

```bash
npx eslint src/shell/AppShell.tsx src/views/projects/ProjectsPage.tsx src/views/subjects/SubjectDashboardPage.tsx src/views/settings/ProjectSettingsPage.tsx src/views/pomodoro/PomodoroPage.tsx src/views/pomodoro/PomodoroWorkbenchGate.tsx
```

from `frontend/`.

Expected: no lint errors.

---

### Task 5: Remove Backend Dirty Terminology And Guard It

**Files:**
- Modify: `tests/test_subjects_api.py`
- Modify or add: `tests/test_spec_alignment.py`
- Modify: `backend/system/api.py`
- Modify: `adapter/mappers.py`
- Modify: `adapter/routers/projects.py`

- [ ] **Step 1: Rename test names**

Rename:

```python
def test_subject_alias_creates_course_compatible_project(...)
```

to:

```python
def test_subject_creates_default_course_material_project(...)
```

- [ ] **Step 2: Add backend/source guard**

Add a static assertion that production backend/frontend code no longer contains the public dirty field string:

```python
def test_no_public_compatibility_project_id_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    checked_paths = [
        root / "adapter",
        root / "backend" / "models",
        root / "backend" / "system",
        root / "frontend" / "src",
    ]
    allowed = {
        str(root / "backend" / "system" / "persistence_json.py"),
    }
    for checked_path in checked_paths:
        for source_path in checked_path.rglob("*"):
            if source_path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            text = source_path.read_text(encoding="utf-8")
            if str(source_path) in allowed:
                continue
            assert "compatibilityProjectId" not in text
            assert "compatibility_project_id" not in text
```

`persistence_json.py` is allowed only because it must read old persisted data.

- [ ] **Step 3: Run source search**

Run:

```bash
rg -n "compatibilityProjectId|compatibility_project_id|compatible project|兼容项目" backend adapter frontend/src tests docs -S
```

Expected after refactor:

- no frontend matches
- no adapter DTO/router matches
- no backend production matches except `persistence_json.py` backward-read fallback
- tests may mention the dirty strings only in guard names/assertions
- docs should not describe the dirty concept as product behavior

---

### Task 6: Update Docs And User-Facing Wording

**Files:**
- Modify: `docs/learningpyramid-user-manual.md`
- Modify: `docs/how-to-create-subject-project.md`

- [ ] **Step 1: Search docs**

Run:

```bash
rg -n "compatibilityProjectId|兼容项目|兼容工作台|兼容入口" docs README.md -S
```

- [ ] **Step 2: Replace wording if found**

Use clean wording:

- `学科` for the top-level learning domain.
- `项目` for a material/workbench entry under a subject.
- `学科设置` for subject-level settings.
- `项目设置` for material/workbench project settings.

Example replacement:

```md
删除学科会一起移除该学科下的项目和本地工作台缓存。
```

Do not mention compatibility projects in user docs.

---

### Task 7: Full Verification

**Files:** No source edits unless verification exposes failures.

- [ ] **Step 1: Backend tests**

Run:

```bash
python -m pytest tests/test_subjects_api.py tests/test_sqlite_store.py tests/test_runtime_backup_restore.py -q
```

Expected: all pass.

- [ ] **Step 2: Frontend/static tests**

Run:

```bash
python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_llm_settings_location.py tests/test_frontend_subject_project_copy.py tests/test_frontend_project_settings_layout.py -q
```

Expected: all pass.

- [ ] **Step 3: Frontend lint**

Run from `frontend/`:

```bash
npx eslint src/ui/api/subjects.ts src/shell/AppShell.tsx src/views/projects/ProjectsPage.tsx src/views/subjects/SubjectDashboardPage.tsx src/views/settings/ProjectSettingsPage.tsx src/views/pomodoro/PomodoroPage.tsx src/views/pomodoro/PomodoroWorkbenchGate.tsx
```

Expected: no lint errors.

- [ ] **Step 4: Frontend build**

Run from `frontend/`:

```bash
npm run build
```

Expected: build completes.

- [ ] **Step 5: Final source scan**

Run:

```bash
rg -n "compatibilityProjectId|compatibility_project_id|compatible project|兼容项目" backend adapter frontend/src tests docs -S
```

Expected: only backward-read persistence fallback and explicit static guard tests remain.

## Risks

- API compatibility: clients expecting `compatibilityProjectId` will break. The project frontend should be updated in the same change.
- Persistence compatibility: old JSON payloads must continue to decode. Do not remove the decode fallback in this round.
- Auth cleanup: material project ownership cleanup must switch to `project_id`; missing this can leave stale auth membership rows.
- Pomodoro: the previous stopgap filters subject root projects. It must be preserved while changing the field source from `compatibilityProjectId` to `subjectProjectId`.
- Conceptual boundary: this plan removes the dirty compatibility concept. It does not introduce a separate non-project `Subject` persistence table; `subjectProjectId` remains the explicit root-project anchor for existing settings/statistics infrastructure.

## Completion Criteria

- No outbound API response contains `compatibilityProjectId`.
- No frontend source references `compatibilityProjectId`.
- New persisted study material records write `projectId`.
- Old persisted study material records with `compatibilityProjectId` still load.
- Subject dashboard, project settings, material deletion, Pomodoro plan selection, and Pomodoro workbench gate still behave as before, but through clean field names.
