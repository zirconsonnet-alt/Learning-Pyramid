import type { PlaybackDescriptor } from "../api/media"
import type { CoursePackageItem } from "./schema"

export function getLocalPackagePlaybackDescriptor({
  instanceId,
  item,
  packageRootUri,
}: {
  instanceId: string
  item: CoursePackageItem
  packageRootUri: string
}): PlaybackDescriptor {
  return {
    instanceId,
    sourceKind: "LOCAL_COURSE_PACKAGE",
    playbackKind: "FILE",
    url: `${packageRootUri.replace(/\/$/, "")}/${item.video.path}`,
    mimeType: "video/mp4",
    durationMs: null,
    supportsFrameGrab: false,
    supportsServerAsr: false,
  }
}
