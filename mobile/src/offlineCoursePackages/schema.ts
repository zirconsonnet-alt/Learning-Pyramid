import { z } from "zod"

const PackageRelativePathSchema = z
  .string()
  .min(1)
  .refine((value) => !value.startsWith("/") && !value.includes("..") && !/^[A-Za-z]:/.test(value), {
    message: "package file paths must be package-relative",
  })

const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/)

export const OfflineCoursePackageQrPayloadSchema = z.object({
  kind: z.literal("learningpyramid.offlineCoursePackage"),
  version: z.literal(1),
  url: z.string().url(),
  token: z.string().min(1),
  expiresAtEpoch: z.number().positive(),
})

export const CoursePackageFileSchema = z.object({
  path: PackageRelativePathSchema,
  sizeBytes: z.number().int().nonnegative(),
  sha256: Sha256Schema,
})

export const CoursePackageSubtitleFileSchema = CoursePackageFileSchema.extend({
  language: z.string().min(1).optional(),
})

export const CoursePackageItemSchema = z.object({
  itemId: z.string().min(1),
  title: z.string().min(1),
  order: z.number().int().positive(),
  learningObjectKey: z.string().min(1),
  video: CoursePackageFileSchema,
  subtitle: CoursePackageSubtitleFileSchema.optional(),
  cover: CoursePackageFileSchema.optional(),
})

export const CoursePackageManifestSchema = z.object({
  manifestVersion: z.literal(1),
  packageId: z.string().min(1),
  title: z.string().min(1),
  createdAt: z.string().min(1),
  subjectId: z.string().min(1),
  scopedProjectId: z.string().min(1),
  source: z.object({
    tool: z.string().min(1),
    version: z.string().min(1),
  }),
  items: z.array(CoursePackageItemSchema).min(1),
})

export const LocalCoursePackageSchema = z.object({
  packageId: z.string().min(1),
  title: z.string().min(1),
  subjectId: z.string().min(1),
  scopedProjectId: z.string().min(1),
  rootUri: z.string().min(1),
  manifest: CoursePackageManifestSchema,
  status: z.enum(["downloading", "verified", "failed"]),
  downloadedAt: z.string().nullable(),
})

export const DownloadTaskSchema = z.object({
  id: z.string().min(1),
  packageId: z.string().min(1),
  relativePath: PackageRelativePathSchema,
  remoteUrl: z.string().url(),
  tempUri: z.string().min(1),
  finalUri: z.string().min(1),
  expectedSizeBytes: z.number().int().nonnegative(),
  expectedSha256: Sha256Schema,
  downloadedBytes: z.number().int().nonnegative(),
  status: z.enum(["queued", "downloading", "paused", "verified", "failed"]),
  lastError: z.string().nullable(),
})

export type OfflineCoursePackageQrPayload = z.infer<typeof OfflineCoursePackageQrPayloadSchema>
export type CoursePackageFile = z.infer<typeof CoursePackageFileSchema>
export type CoursePackageItem = z.infer<typeof CoursePackageItemSchema>
export type CoursePackageManifest = z.infer<typeof CoursePackageManifestSchema>
export type LocalCoursePackage = z.infer<typeof LocalCoursePackageSchema>
export type DownloadTask = z.infer<typeof DownloadTaskSchema>
