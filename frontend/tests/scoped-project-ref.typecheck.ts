import { projectApiPath, type ScopedProjectRef } from "../src/ui/api/projectScope"
import { buildProjectSettingsPath, buildProjectWorkbenchPath, buildScopedProjectPath } from "../src/ui/projectPaths"

const ref: ScopedProjectRef = {
  subjectId: "subj_000003",
  scopedProjectId: "proj_000001",
}

projectApiPath(ref, "/instances")
buildScopedProjectPath(ref.subjectId, ref.scopedProjectId, "/workbench")
buildProjectSettingsPath(ref.subjectId, ref.scopedProjectId)
buildProjectWorkbenchPath(ref.subjectId, ref.scopedProjectId)

// @ts-expect-error ScopedProjectRef must not accept the old ambiguous projectId field.
const oldRef: ScopedProjectRef = { subjectId: "subj_000003", projectId: "proj_000001" }

// Keep the variable referenced so noUnusedLocals can protect this typecheck file.
void oldRef
