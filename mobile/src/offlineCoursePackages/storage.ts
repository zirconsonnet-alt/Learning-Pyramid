import { Directory, File, Paths } from "expo-file-system"

import { CoursePackageManifestSchema, type CoursePackageManifest, type LocalCoursePackage } from "./schema"

const PACKAGE_LIBRARY_DIR = "learningpyramid-course-packages"
const DEFAULT_SPACE_RESERVE_BYTES = 100 * 1024 * 1024

function pathSegment(value: string) {
  return encodeURIComponent(value)
}

export function buildCoursePackageRoot(subjectId: string, scopedProjectId: string, packageId: string) {
  return new Directory(
    Paths.document,
    PACKAGE_LIBRARY_DIR,
    pathSegment(subjectId),
    pathSegment(scopedProjectId),
    pathSegment(packageId),
  )
}

export function buildCourseProjectRoot(subjectId: string, scopedProjectId: string) {
  return new Directory(Paths.document, PACKAGE_LIBRARY_DIR, pathSegment(subjectId), pathSegment(scopedProjectId))
}

export function ensureFreeSpace(requiredBytes: number, reserveBytes = DEFAULT_SPACE_RESERVE_BYTES) {
  const available = Number(Paths.availableDiskSpace)
  if (!Number.isFinite(available) || available <= 0) {
    throw new Error("无法读取手机剩余空间。")
  }
  if (available < Math.max(0, requiredBytes) + Math.max(0, reserveBytes)) {
    throw new Error("手机剩余空间不足。")
  }
}

export async function writeLocalManifest(manifest: CoursePackageManifest) {
  const parsed = CoursePackageManifestSchema.parse(manifest)
  const root = buildCoursePackageRoot(parsed.subjectId, parsed.scopedProjectId, parsed.packageId)
  root.create({ idempotent: true, intermediates: true })
  const file = new File(root, "manifest.json")
  file.create({ overwrite: true, intermediates: true })
  file.write(JSON.stringify(parsed, null, 2))
  return file
}

export function readLocalManifest(root: Directory) {
  const file = new File(root, "manifest.json")
  return CoursePackageManifestSchema.parse(JSON.parse(file.textSync()))
}

export function listLocalPackages(subjectId: string, scopedProjectId: string): LocalCoursePackage[] {
  const projectRoot = buildCourseProjectRoot(subjectId, scopedProjectId)
  if (!projectRoot.exists) return []
  return projectRoot
    .list()
    .filter((entry): entry is Directory => entry instanceof Directory)
    .map((root) => {
      const manifest = readLocalManifest(root)
      return {
        packageId: manifest.packageId,
        title: manifest.title,
        subjectId: manifest.subjectId,
        scopedProjectId: manifest.scopedProjectId,
        rootUri: root.uri,
        manifest,
        status: "verified",
        downloadedAt: null,
      }
    })
}

export function deleteLocalPackage(manifest: CoursePackageManifest) {
  const parsed = CoursePackageManifestSchema.parse(manifest)
  const root = buildCoursePackageRoot(parsed.subjectId, parsed.scopedProjectId, parsed.packageId)
  root.delete()
}
