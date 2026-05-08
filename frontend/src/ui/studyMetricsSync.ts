import { type DailyStudyMetricEntry, syncMyStudyMetrics } from "@/ui/api/profile"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { listDailyStudyMetricEntries, mergeDailyStudyMetricEntries } from "@/ui/store/workbenchDailyStats"

function normalizeProjectIds(projectIds: string[]) {
  return Array.from(
    new Set(
      projectIds
        .map((projectId) => projectId.trim())
        .filter((projectId) => Boolean(projectId) && !isVirtualStudyReviewProjectId(projectId)),
    ),
  )
}

export async function syncStudyMetricsSnapshot(params: {
  projectIds: string[]
  dateFrom?: string
  dateTo?: string
}) {
  const projectIds = normalizeProjectIds(params.projectIds)
  if (projectIds.length === 0) return [] as DailyStudyMetricEntry[]

  const entries = listDailyStudyMetricEntries(projectIds, {
    dateFrom: params.dateFrom,
    dateTo: params.dateTo,
  })
  const merged = await syncMyStudyMetrics({
    projectIds,
    dateFrom: params.dateFrom,
    dateTo: params.dateTo,
    entries,
  })
  mergeDailyStudyMetricEntries(merged)
  return merged
}
