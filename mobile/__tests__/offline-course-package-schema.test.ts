import { CoursePackageManifestSchema, OfflineCoursePackageQrPayloadSchema } from "../src/offlineCoursePackages/schema"

describe("offline course package schema", () => {
  it("accepts a token-gated LAN QR payload", () => {
    const payload = OfflineCoursePackageQrPayloadSchema.parse({
      kind: "learningpyramid.offlineCoursePackage",
      version: 1,
      url: "http://192.168.1.8:23456",
      token: "secret",
      expiresAtEpoch: 4102444800,
    })

    expect(payload.url).toBe("http://192.168.1.8:23456")
  })

  it("accepts a manifest bound to a scoped project", () => {
    const manifest = CoursePackageManifestSchema.parse({
      manifestVersion: 1,
      packageId: "pkg_1",
      title: "课程",
      createdAt: "2026-05-20T12:00:00Z",
      subjectId: "subj_1",
      scopedProjectId: "proj_1",
      source: { tool: "LearningPyramid-SubtitleTool", version: "local" },
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
    })

    expect(manifest.subjectId).toBe("subj_1")
    expect(manifest.items[0].video.path).toBe("videos/01.mp4")
  })

  it("rejects absolute package file paths", () => {
    expect(() =>
      CoursePackageManifestSchema.parse({
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
            video: { path: "/videos/01.mp4", sizeBytes: 3, sha256: "0".repeat(64) },
          },
        ],
      }),
    ).toThrow()
  })
})
