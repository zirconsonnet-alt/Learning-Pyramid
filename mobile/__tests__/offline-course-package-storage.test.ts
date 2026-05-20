const mockCreatedDirectories: string[] = []
const mockCreatedFiles: string[] = []
const mockWrites = new Map<string, string>()
const mockDeletedDirectories: string[] = []

jest.mock("expo-file-system", () => {
  class Directory {
    uri: string
    exists = true

    constructor(...parts: Array<string | { uri: string }>) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri)).join("/").replace(/\/+/g, "/")
      if (this.uri.startsWith("file:/")) this.uri = this.uri.replace("file:/", "file:///")
    }

    create() {
      mockCreatedDirectories.push(this.uri)
    }

    delete() {
      mockDeletedDirectories.push(this.uri)
    }

    list() {
      return []
    }
  }

  class File {
    uri: string

    constructor(...parts: Array<string | { uri: string }>) {
      this.uri = parts.map((part) => (typeof part === "string" ? part : part.uri)).join("/").replace(/\/+/g, "/")
      if (this.uri.startsWith("file:/")) this.uri = this.uri.replace("file:/", "file:///")
    }

    create() {
      mockCreatedFiles.push(this.uri)
    }

    write(content: string) {
      mockWrites.set(this.uri, content)
    }
  }

  return {
    Directory,
    File,
    Paths: {
      availableDiskSpace: 1024 * 1024 * 1024,
      document: new Directory("file:///document"),
    },
  }
})

import { buildCoursePackageRoot, deleteLocalPackage, ensureFreeSpace, writeLocalManifest } from "../src/offlineCoursePackages/storage"
import type { CoursePackageManifest } from "../src/offlineCoursePackages/schema"

const manifest: CoursePackageManifest = {
  manifestVersion: 1,
  packageId: "pkg_1",
  title: "课程",
  createdAt: "2026-05-20T12:00:00Z",
  subjectId: "subj_1",
  scopedProjectId: "proj_1",
  source: { tool: "tool", version: "local" },
  items: [
    {
      itemId: "lesson_1",
      title: "第一讲",
      order: 1,
      learningObjectKey: "lesson_1",
      video: { path: "videos/01.mp4", sizeBytes: 3, sha256: "0".repeat(64) },
    },
  ],
}

beforeEach(() => {
  mockCreatedDirectories.length = 0
  mockCreatedFiles.length = 0
  mockDeletedDirectories.length = 0
  mockWrites.clear()
})

describe("offline course package storage", () => {
  it("builds an app-private project-scoped package root", () => {
    const root = buildCoursePackageRoot("subj_1", "proj_1", "pkg_1")

    expect(root.uri).toContain("learningpyramid-course-packages/subj_1/proj_1/pkg_1")
  })

  it("writes a validated manifest into the package root", async () => {
    const file = await writeLocalManifest(manifest)

    expect(mockCreatedDirectories[0]).toContain("learningpyramid-course-packages/subj_1/proj_1/pkg_1")
    expect(mockCreatedFiles[0]).toContain("manifest.json")
    expect(JSON.parse(mockWrites.get(file.uri) ?? "{}").packageId).toBe("pkg_1")
  })

  it("checks free space with explicit reserve bytes", () => {
    expect(() => ensureFreeSpace(1024, 1024)).not.toThrow()
    expect(() => ensureFreeSpace(2 * 1024 * 1024 * 1024, 1024)).toThrow("手机剩余空间不足")
  })

  it("deletes only the package root for the manifest identity", () => {
    deleteLocalPackage(manifest)

    expect(mockDeletedDirectories).toEqual([expect.stringContaining("learningpyramid-course-packages/subj_1/proj_1/pkg_1")])
  })
})
