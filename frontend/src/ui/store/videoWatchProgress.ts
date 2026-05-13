import {
  fetchVideoWatchProgressMap,
  markVideoWatchProgressCompleted as markRemoteVideoWatchProgressCompleted,
  syncVideoWatchProgressRange as syncRemoteVideoWatchProgressRange,
  type VideoWatchProgress,
} from "@/ui/api/instances"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { loadVideoWatchCoverageMap, recordVideoWatchCoverageRange } from "@/ui/store/videoWatchCoverage"

export type VideoWatchProgressMap = Record<string, VideoWatchProgress>

export function loadVideoWatchProgressMap(
  projectId: string,
  instanceIds: string[],
  durationByInstanceId?: Record<string, number | null | undefined>,
  remoteProgressByInstanceId?: VideoWatchProgressMap | null,
) {
  const localCoverage = loadVideoWatchCoverageMap(projectId, instanceIds, durationByInstanceId)
  const out: Record<string, number> = { ...localCoverage }
  for (const instanceId of instanceIds) {
    const remote = remoteProgressByInstanceId?.[instanceId]
    if (!remote) continue
    const durationMs = durationByInstanceId?.[instanceId] ?? remote.durationMs ?? 0
    const remoteWatchedMs = remote.completedAt && durationMs > 0 ? durationMs : Math.max(0, remote.watchedMs)
    out[instanceId] = Math.max(out[instanceId] ?? 0, durationMs > 0 ? Math.min(durationMs, remoteWatchedMs) : remoteWatchedMs)
  }
  return out
}

export async function fetchPersistentVideoWatchProgressMap(
  scope: ScopedProjectRef,
  projectId: string,
  instanceIds: string[],
  signal?: AbortSignal,
) {
  if (!projectId || instanceIds.length === 0) return {} as VideoWatchProgressMap
  return fetchVideoWatchProgressMap(scope, instanceIds, { signal, timeoutMs: 90_000 })
}

export function syncVideoWatchProgressRange(
  scope: ScopedProjectRef,
  projectId: string,
  instanceId: string,
  startMs: number,
  endMs: number,
  durationMs?: number | null,
) {
  const watchedMs = recordVideoWatchCoverageRange(projectId, instanceId, startMs, endMs, durationMs)
  void syncRemoteVideoWatchProgressRange(scope, instanceId, { startMs, endMs, durationMs }).catch(() => undefined)
  return watchedMs
}

export function markVideoWatchProgressCompleted(scope: ScopedProjectRef, projectId: string, instanceId: string, durationMs: number) {
  const safeDurationMs = Math.max(0, Math.floor(durationMs))
  if (safeDurationMs <= 0) return 0
  const watchedMs = recordVideoWatchCoverageRange(projectId, instanceId, 0, safeDurationMs, safeDurationMs)
  void markRemoteVideoWatchProgressCompleted(scope, instanceId, { durationMs: safeDurationMs }).catch(() => undefined)
  return watchedMs
}
