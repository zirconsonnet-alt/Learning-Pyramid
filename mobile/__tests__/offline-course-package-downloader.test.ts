import { buildDownloadTasks, bytesToHex, markTaskFailed, markTaskPaused } from "../src/offlineCoursePackages/downloader"
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
      subtitle: { path: "subtitles/01.srt", language: "zh-CN", sizeBytes: 2, sha256: "1".repeat(64) },
    },
  ],
}

describe("offline package downloader", () => {
  it("builds one file task per selected manifest file", () => {
    const tasks = buildDownloadTasks({
      manifest,
      selectedItemIds: ["lesson_1"],
      baseUrl: "http://127.0.0.1:1234",
      token: "secret",
      packageRootUri: "file://root",
    })

    expect(tasks.map((task) => task.relativePath)).toEqual(["videos/01.mp4", "subtitles/01.srt"])
    expect(tasks[0].remoteUrl).toBe("http://127.0.0.1:1234/files/videos/01.mp4")
  })

  it("keeps task transitions explicit", () => {
    const task = buildDownloadTasks({
      manifest,
      selectedItemIds: ["lesson_1"],
      baseUrl: "http://127.0.0.1:1234",
      token: "secret",
      packageRootUri: "file://root",
    })[0]

    expect(markTaskPaused(task).status).toBe("paused")
    expect(markTaskFailed(task, "hash mismatch").lastError).toBe("hash mismatch")
  })

  it("converts bytes to lowercase hex", () => {
    expect(bytesToHex(new Uint8Array([0, 10, 255]))).toBe("000aff")
  })
})
