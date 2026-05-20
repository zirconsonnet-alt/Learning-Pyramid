import type { CoursePackageFile, CoursePackageManifest, DownloadTask } from "./schema"

function taskForFile(input: {
  baseUrl: string
  entry: CoursePackageFile
  packageId: string
  packageRootUri: string
}): DownloadTask {
  const cleanPath = input.entry.path.replace(/^\/+/, "")
  return {
    id: `${input.packageId}:${cleanPath}`,
    packageId: input.packageId,
    relativePath: cleanPath,
    remoteUrl: `${input.baseUrl.replace(/\/$/, "")}/files/${encodeURI(cleanPath)}`,
    tempUri: `${input.packageRootUri.replace(/\/$/, "")}/download-state/${cleanPath}.part`,
    finalUri: `${input.packageRootUri.replace(/\/$/, "")}/${cleanPath}`,
    expectedSizeBytes: input.entry.sizeBytes,
    expectedSha256: input.entry.sha256,
    downloadedBytes: 0,
    status: "queued",
    lastError: null,
  }
}

export function buildDownloadTasks(input: {
  baseUrl: string
  manifest: CoursePackageManifest
  packageRootUri: string
  selectedItemIds: string[]
  token: string
}): DownloadTask[] {
  const selected = new Set(input.selectedItemIds)
  return input.manifest.items
    .filter((item) => selected.has(item.itemId))
    .flatMap((item) => [item.video, item.subtitle, item.cover].filter((entry): entry is CoursePackageFile => Boolean(entry)))
    .map((entry) =>
      taskForFile({
        baseUrl: input.baseUrl,
        entry,
        packageId: input.manifest.packageId,
        packageRootUri: input.packageRootUri,
      }),
    )
}

export function markTaskPaused(task: DownloadTask): DownloadTask {
  return { ...task, status: "paused" }
}

export function markTaskFailed(task: DownloadTask, error: string): DownloadTask {
  return { ...task, status: "failed", lastError: error }
}

export function bytesToHex(bytes: Uint8Array) {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}
