import { z } from "zod"

import { ApiError, apiRequest, getBaseUrl, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { DesktopAgentSchema } from "@/ui/api/desktopAgents"

export const SystemCapabilitiesSchema = z.object({
  appMode: z.enum(["local", "hosted"]),
  asrEnabled: z.boolean(),
  serverMediaStreamEnabled: z.boolean(),
  browserLocalMediaEnabled: z.boolean(),
  authEnabled: z.boolean(),
  allowSignup: z.boolean(),
})
export type SystemCapabilities = z.infer<typeof SystemCapabilitiesSchema>

export function getSystemCapabilities(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/capabilities",
    responseSchema: SystemCapabilitiesSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

const DesktopAgentRelayRuntimeSchema = z
  .object({
    alertWebhook: z
      .object({
        channels: z
          .array(
            z.object({
              name: z.string(),
              url: z.string(),
              status: z.enum(["IDLE", "HEALTHY", "FAILED", "RETRYING"]),
              lastAttemptAt: z.string().nullable().default(null),
              lastSuccessAt: z.string().nullable().default(null),
              lastError: z.string().nullable().default(null),
              sentCount: z.number().int().nonnegative().default(0),
              suppressedCount: z.number().int().nonnegative().default(0),
              failedCount: z.number().int().nonnegative().default(0),
              lastAlertCount: z.number().int().nonnegative().default(0),
              nextRetryAt: z.string().nullable().default(null),
              retryPending: z.boolean().default(false),
              consecutiveFailureCount: z.number().int().nonnegative().default(0),
            }),
          )
          .default([]),
        configured: z.boolean().default(false),
        windowHours: z.number().int().nonnegative().default(0),
        cooldownSeconds: z.number().int().nonnegative().default(0),
        retryBackoffSeconds: z.number().int().nonnegative().default(0),
        retryMaxBackoffSeconds: z.number().int().nonnegative().default(0),
        channelCount: z.number().int().nonnegative().default(0),
        healthyChannelCount: z.number().int().nonnegative().default(0),
        retryingChannelCount: z.number().int().nonnegative().default(0),
        failingChannelCount: z.number().int().nonnegative().default(0),
        lastAttemptAt: z.string().nullable().default(null),
        lastSuccessAt: z.string().nullable().default(null),
        lastError: z.string().nullable().default(null),
        sentCount: z.number().int().nonnegative().default(0),
        suppressedCount: z.number().int().nonnegative().default(0),
        failedCount: z.number().int().nonnegative().default(0),
        lastAlertCount: z.number().int().nonnegative().default(0),
      })
      .default({
        channels: [],
        configured: false,
        windowHours: 0,
        cooldownSeconds: 0,
        retryBackoffSeconds: 0,
        retryMaxBackoffSeconds: 0,
        channelCount: 0,
        healthyChannelCount: 0,
        retryingChannelCount: 0,
        failingChannelCount: 0,
        lastAttemptAt: null,
        lastSuccessAt: null,
        lastError: null,
        sentCount: 0,
        suppressedCount: 0,
        failedCount: 0,
        lastAlertCount: 0,
      }),
    available: z.boolean(),
    connectedAgentCount: z.number().int().nonnegative().default(0),
    connectedAgentIds: z.array(z.string()).default([]),
    queuedCommandCount: z.number().int().nonnegative().default(0),
    streamSessionCount: z.number().int().nonnegative().default(0),
    activeStreamCount: z.number().int().nonnegative().default(0),
    terminalStreamCount: z.number().int().nonnegative().default(0),
    probeRequestCount: z.number().int().nonnegative().default(0),
    pendingProbeCount: z.number().int().nonnegative().default(0),
    hlsJobCount: z.number().int().nonnegative().default(0),
    activeHlsJobCount: z.number().int().nonnegative().default(0),
    hlsJobsByState: z.record(z.string(), z.number().int().nonnegative()).default({}),
    hlsJobReasonCounts: z.record(z.string(), z.number().int().nonnegative()).default({}),
    hlsCacheRequestCount: z.number().int().nonnegative().default(0),
    hlsCacheHitCount: z.number().int().nonnegative().default(0),
    hlsCacheMissCount: z.number().int().nonnegative().default(0),
    hlsCacheHitRate: z.number().min(0).max(1).nullable().default(null),
    hlsArtifactRequestCount: z.number().int().nonnegative().default(0),
    hlsArtifactBytesServed: z.number().int().nonnegative().default(0),
    hlsCacheEntryCount: z.number().int().nonnegative().default(0),
    hlsCacheBytes: z.number().int().nonnegative().default(0),
    hlsCachePrunedCount: z.number().int().nonnegative().default(0),
    persistedHlsJobAuditCount: z.number().int().nonnegative().default(0),
    persistedExpiredHlsJobCount: z.number().int().nonnegative().default(0),
    metricSampleBucketSeconds: z.number().int().nonnegative().default(0),
    metricSampleRetentionDays: z.number().int().nonnegative().default(0),
    persistedMetricSampleCount: z.number().int().nonnegative().default(0),
    persistedDiagnosticEventCount: z.number().int().nonnegative().default(0),
    sampledMetricProjectCount: z.number().int().nonnegative().default(0),
    prunedMetricSampleCount: z.number().int().nonnegative().default(0),
    prunedDiagnosticEventCount: z.number().int().nonnegative().default(0),
    reapedStreamCount: z.number().int().nonnegative().default(0),
    reapedProbeCount: z.number().int().nonnegative().default(0),
    reapedHlsJobCount: z.number().int().nonnegative().default(0),
    reapReasonCounts: z.record(z.string(), z.number().int().nonnegative()).default({}),
    lastReapedAt: z.string().nullable().default(null),
    expiredStreamIds: z.array(z.string()).default([]),
    expiredProbeIds: z.array(z.string()).default([]),
    expiredHlsJobIds: z.array(z.string()).default([]),
  })
  .passthrough()

export const SystemRuntimeSchema = z
  .object({
    status: z.string(),
    appMode: z.enum(["local", "hosted"]),
    authEnabled: z.boolean(),
    allowSignup: z.boolean(),
    asrEnabled: z.boolean(),
    serverMediaStreamEnabled: z.boolean(),
    browserLocalMediaEnabled: z.boolean(),
    sqlBackend: z.string(),
    desktopAgentRelay: DesktopAgentRelayRuntimeSchema,
  })
  .passthrough()
export type SystemRuntime = z.infer<typeof SystemRuntimeSchema> & { ready: boolean }

const RelayMonitorAgentSchema = DesktopAgentSchema.extend({
  connected: z.boolean(),
  queuedCommandCount: z.number().int().nonnegative(),
  activeStreamCount: z.number().int().nonnegative(),
  pendingProbeCount: z.number().int().nonnegative(),
  activeHlsJobCount: z.number().int().nonnegative(),
  hlsJobCount: z.number().int().nonnegative(),
})

const RelayMonitorIssueSchema = z.object({
  streamId: z.string(),
  projectId: z.string(),
  projectTitle: z.string().nullable().optional(),
  instanceId: z.string(),
  agentId: z.string(),
  mode: z.string(),
  status: z.enum(["FAILED", "CANCELLED"]),
  rangeStart: z.number().int().nonnegative().nullable(),
  rangeEnd: z.number().int().nonnegative().nullable(),
  bytesFromAgent: z.number().int().nonnegative(),
  bytesToViewer: z.number().int().nonnegative(),
  createdAt: z.string(),
  updatedAt: z.string(),
  expiresAt: z.string(),
  finishedAt: z.string().nullable(),
  failureReason: z.string().nullable(),
})

const RelayMonitorHlsJobSchema = z.object({
  jobId: z.string(),
  cacheKey: z.string(),
  agentId: z.string(),
  projectId: z.string(),
  instanceId: z.string(),
  relativePath: z.string(),
  profile: z.record(z.string(), z.union([z.string(), z.number().int()])),
  createdAt: z.string(),
  updatedAt: z.string(),
  expiresAt: z.string(),
  state: z.string(),
  message: z.string().nullable(),
  startedAt: z.string().nullable().optional(),
  finishedAt: z.string().nullable().optional(),
  lastArtifactAt: z.string().nullable().optional(),
  artifactCount: z.number().int().nonnegative().default(0),
  artifactBytes: z.number().int().nonnegative().default(0),
})

const RelayMonitorTrendPointSchema = z.object({
  bucketStart: z.string(),
  capturedAt: z.string(),
  bucketSeconds: z.number().int().nonnegative().default(0),
  activeStreamCount: z.number().int().nonnegative(),
  activeHlsJobCount: z.number().int().nonnegative(),
  cacheEntryCount: z.number().int().nonnegative(),
  cacheBytes: z.number().int().nonnegative(),
  uploadBytes: z.number().int().nonnegative(),
  viewerBytes: z.number().int().nonnegative(),
  artifactBytes: z.number().int().nonnegative(),
  completedStreams: z.number().int().nonnegative(),
  failedStreams: z.number().int().nonnegative(),
  cancelledStreams: z.number().int().nonnegative(),
  completedHlsJobs: z.number().int().nonnegative(),
  failedHlsJobs: z.number().int().nonnegative(),
  cancelledHlsJobs: z.number().int().nonnegative(),
})

const RelayMonitorTrendWindowSchema = z.object({
  pointCount: z.number().int().nonnegative(),
  uploadBytes: z.number().int().nonnegative(),
  viewerBytes: z.number().int().nonnegative(),
  artifactBytes: z.number().int().nonnegative(),
  completedStreams: z.number().int().nonnegative(),
  failedStreams: z.number().int().nonnegative(),
  cancelledStreams: z.number().int().nonnegative(),
  completedHlsJobs: z.number().int().nonnegative(),
  failedHlsJobs: z.number().int().nonnegative(),
  cancelledHlsJobs: z.number().int().nonnegative(),
  peakActiveStreams: z.number().int().nonnegative(),
  peakActiveHlsJobs: z.number().int().nonnegative(),
  peakCacheBytes: z.number().int().nonnegative(),
  latestCacheBytes: z.number().int().nonnegative(),
})

const RelayMonitorDiagnosticSchema = z.object({
  eventId: z.string(),
  agentId: z.string(),
  projectId: z.string().nullable(),
  instanceId: z.string().nullable(),
  relativePath: z.string().nullable(),
  level: z.string(),
  category: z.string(),
  eventType: z.string(),
  message: z.string(),
  details: z.record(z.string(), z.unknown()).default({}),
  createdAt: z.string(),
})

const RelayMonitorAlertSchema = z.object({
  severity: z.enum(["error", "warning"]),
  code: z.string(),
  title: z.string(),
  message: z.string(),
  agentId: z.string().nullable().optional(),
  projectId: z.string().nullable().optional(),
  observedAt: z.string(),
  count: z.number().int().nonnegative(),
})

const RelayMonitorBindingSummarySchema = z.object({
  desktopAgentProjectCount: z.number().int().nonnegative(),
  boundOnlineProjectCount: z.number().int().nonnegative(),
  boundOfflineProjectCount: z.number().int().nonnegative(),
  serverFsProjectCount: z.number().int().nonnegative(),
  supersededBindingCount: z.number().int().nonnegative(),
})

const RelayMonitorProjectBindingSchema = z.object({
  projectId: z.string(),
  projectTitle: z.string(),
  sourceKind: z.string(),
  desktopAgentId: z.string().nullable(),
  sourceRootLabel: z.string().nullable(),
  deviceName: z.string().nullable(),
  appVersion: z.string().nullable(),
  lastSeenAt: z.string().nullable(),
  pairedAt: z.string().nullable(),
  connected: z.boolean(),
  bindingState: z.enum(["ONLINE", "OFFLINE", "UNBOUND"]),
  supersededByAgentId: z.string().nullable(),
})

export const RelayMonitorSchema = z.object({
  available: z.boolean(),
  projectCount: z.number().int().nonnegative(),
  projectIds: z.array(z.string()).default([]),
  bindingSummary: RelayMonitorBindingSummarySchema,
  projectBindings: z.array(RelayMonitorProjectBindingSchema).default([]),
  agentCount: z.number().int().nonnegative(),
  agents: z.array(RelayMonitorAgentSchema).default([]),
  streamSummary: z.object({
    sessionCount: z.number().int().nonnegative(),
    activeSessionCount: z.number().int().nonnegative(),
    failedSessionCount: z.number().int().nonnegative(),
    cancelledSessionCount: z.number().int().nonnegative(),
    completedSessionCount: z.number().int().nonnegative(),
    bytesFromAgentTotal: z.number().int().nonnegative(),
    bytesToViewerTotal: z.number().int().nonnegative(),
    sessionsByStatus: z.record(z.string(), z.number().int().nonnegative()).default({}),
    issueReasonCounts: z.record(z.string(), z.number().int().nonnegative()).default({}),
  }),
  recentIssues: z.array(RelayMonitorIssueSchema).default([]),
  hlsSummary: z.object({
    jobCount: z.number().int().nonnegative(),
    activeHlsJobCount: z.number().int().nonnegative(),
    jobsByState: z.record(z.string(), z.number().int().nonnegative()).default({}),
    issueReasonCounts: z.record(z.string(), z.number().int().nonnegative()).default({}),
    activityWindows: z
      .object({
        lastHour: z.object({
          jobCount: z.number().int().nonnegative(),
          completedCount: z.number().int().nonnegative(),
          failedCount: z.number().int().nonnegative(),
          cancelledCount: z.number().int().nonnegative(),
          artifactBytes: z.number().int().nonnegative(),
        }),
        lastDay: z.object({
          jobCount: z.number().int().nonnegative(),
          completedCount: z.number().int().nonnegative(),
          failedCount: z.number().int().nonnegative(),
          cancelledCount: z.number().int().nonnegative(),
          artifactBytes: z.number().int().nonnegative(),
        }),
      })
      .default({
        lastHour: { jobCount: 0, completedCount: 0, failedCount: 0, cancelledCount: 0, artifactBytes: 0 },
        lastDay: { jobCount: 0, completedCount: 0, failedCount: 0, cancelledCount: 0, artifactBytes: 0 },
      }),
  }),
  recentHlsJobs: z.array(RelayMonitorHlsJobSchema).default([]),
  diagnosticSummary: z.object({
    eventCount: z.number().int().nonnegative(),
    errorCount: z.number().int().nonnegative(),
    warningCount: z.number().int().nonnegative(),
    eventsByCategory: z.record(z.string(), z.number().int().nonnegative()).default({}),
    eventsByLevel: z.record(z.string(), z.number().int().nonnegative()).default({}),
    eventsByType: z.record(z.string(), z.number().int().nonnegative()).default({}),
  }),
  recentDiagnostics: z.array(RelayMonitorDiagnosticSchema).default([]),
  alerts: z.array(RelayMonitorAlertSchema).default([]),
  trends: z.object({
    sampleBucketSeconds: z.number().int().nonnegative(),
    retentionDays: z.number().int().nonnegative().default(0),
    sampleCount: z.number().int().nonnegative(),
    sampledProjectCount: z.number().int().nonnegative(),
    latestCapturedAt: z.string().nullable(),
    historyStartAt: z.string().nullable(),
    windows: z.object({
      last6Hours: RelayMonitorTrendWindowSchema,
      lastDay: RelayMonitorTrendWindowSchema,
      last7Days: RelayMonitorTrendWindowSchema,
      last30Days: RelayMonitorTrendWindowSchema,
    }),
    timelines: z.object({
      last6Hours: z.array(RelayMonitorTrendPointSchema).default([]),
      lastDay: z.array(RelayMonitorTrendPointSchema).default([]),
      last7Days: z.array(RelayMonitorTrendPointSchema).default([]),
      last30Days: z.array(RelayMonitorTrendPointSchema).default([]),
    }),
  }),
})
export type RelayMonitor = z.infer<typeof RelayMonitorSchema>

export type RelayMonitorQuery = {
  diagnosticSinceHours?: number
  diagnosticLimit?: number
  alertSinceHours?: number
  diagnosticLevel?: string | null
  diagnosticCategory?: string | null
  diagnosticEventType?: string | null
  diagnosticAgentId?: string | null
  diagnosticProjectId?: string | null
  diagnosticQuery?: string | null
}

const DesktopAgentReleaseAssetSchema = z.object({
  name: z.string(),
  version: z.string(),
  kind: z.enum(["installer_exe", "installer_zip", "standalone_zip"]),
  sizeBytes: z.number().int().nonnegative(),
  sha256: z.string(),
  integrityMode: z.string().default("sha256"),
  publishedAt: z.string(),
  downloadPath: z.string(),
  signature: z
    .object({
      status: z.string(),
      subject: z.string().nullable().default(null),
      issuer: z.string().nullable().default(null),
      thumbprint: z.string().nullable().default(null),
      signedAt: z.string().nullable().default(null),
      source: z.string().nullable().default(null),
    })
    .default({
      status: "UNKNOWN",
      subject: null,
      issuer: null,
      thumbprint: null,
      signedAt: null,
      source: null,
    }),
  silentInstall: z
    .object({
      supported: z.boolean().default(false),
      strategy: z.string().default("unsupported"),
      relaunch: z.boolean().default(false),
    })
    .default({
      supported: false,
      strategy: "unsupported",
      relaunch: false,
    }),
  releaseNotes: z.string().nullable().optional(),
})

const DesktopAgentLatestReleaseSchema = z.object({
  version: z.string(),
  publishedAt: z.string(),
  assetCount: z.number().int().nonnegative(),
  preferredAsset: DesktopAgentReleaseAssetSchema.nullable(),
  assets: z.array(DesktopAgentReleaseAssetSchema),
  releaseNotes: z.string().nullable().optional(),
})

const DesktopAgentReleasePolicySchema = z
  .object({
    requireSigned: z.boolean().default(false),
    acceptedSignatureStatuses: z.array(z.string()).default([]),
    rejectedAssetCount: z.number().int().nonnegative().default(0),
    visibleAssetCount: z.number().int().nonnegative().default(0),
    totalAssetCount: z.number().int().nonnegative().default(0),
  })
  .default({
    requireSigned: false,
    acceptedSignatureStatuses: [],
    rejectedAssetCount: 0,
    visibleAssetCount: 0,
    totalAssetCount: 0,
  })

export const DesktopAgentReleaseSchema = z.object({
  available: z.boolean(),
  requestedVersion: z.string().nullable(),
  updateAvailable: z.boolean(),
  latest: DesktopAgentLatestReleaseSchema.nullable(),
  policy: DesktopAgentReleasePolicySchema,
})
export type DesktopAgentRelease = z.infer<typeof DesktopAgentReleaseSchema>

const DesktopAgentSetupCandidateRootSchema = z.object({
  rootKey: z.string(),
  relativePath: z.string().default(""),
  label: z.string(),
  sourceRootLabel: z.string().nullable(),
})

const DesktopAgentSetupProjectSchema = z.object({
  projectId: z.string(),
  title: z.string(),
  state: z.string(),
  projectRoot: z.string(),
  learningObjectRoot: z.string(),
  sourceKind: z.string(),
  desktopAgentId: z.string().nullable(),
  sourceRootLabel: z.string().nullable(),
  candidateRoots: z.array(DesktopAgentSetupCandidateRootSchema).default([]),
})

export const DesktopAgentSetupCatalogSchema = z.object({
  projectCount: z.number().int().nonnegative(),
  projects: z.array(DesktopAgentSetupProjectSchema).default([]),
})
export type DesktopAgentSetupCatalog = z.infer<typeof DesktopAgentSetupCatalogSchema>

export const DesktopAgentSetupSessionSchema = z.object({
  setupCode: z.string(),
  expiresAt: z.string(),
  preferredProjectId: z.string().nullable(),
})
export type DesktopAgentSetupSession = z.infer<typeof DesktopAgentSetupSessionSchema>

const SystemRuntimeEnvelopeSchema = z.object({
  ok: z.boolean(),
  data: SystemRuntimeSchema,
})

function buildRelayMonitorSearch(query?: RelayMonitorQuery) {
  if (!query) return ""
  const params = new URLSearchParams()
  const appendText = (key: string, value: string | null | undefined) => {
    const normalized = value?.trim()
    if (normalized) params.set(key, normalized)
  }
  const appendNumber = (key: string, value: number | null | undefined) => {
    if (value == null || !Number.isFinite(value) || value <= 0) return
    params.set(key, String(Math.trunc(value)))
  }
  appendNumber("diagnosticSinceHours", query.diagnosticSinceHours)
  appendNumber("diagnosticLimit", query.diagnosticLimit)
  appendNumber("alertSinceHours", query.alertSinceHours)
  appendText("diagnosticLevel", query.diagnosticLevel)
  appendText("diagnosticCategory", query.diagnosticCategory)
  appendText("diagnosticEventType", query.diagnosticEventType)
  appendText("diagnosticAgentId", query.diagnosticAgentId)
  appendText("diagnosticProjectId", query.diagnosticProjectId)
  appendText("diagnosticQuery", query.diagnosticQuery)
  const search = params.toString()
  return search ? `?${search}` : ""
}

export async function getSystemRuntime(options?: ApiRequestExecutionOptions): Promise<SystemRuntime> {
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const timeoutMs = options?.timeoutMs ?? 12_000
  let timedOut = false
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null

  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort()
    } else {
      const onAbort = () => controller.abort()
      options.signal.addEventListener("abort", onAbort, { once: true })
      listeners.push(() => options.signal?.removeEventListener("abort", onAbort))
    }
  }

  timeoutId = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  let res: Response
  let text: string
  try {
    res = await fetch(`${getBaseUrl()}/system/runtime`, {
      method: "GET",
      credentials: "include",
      signal: controller.signal,
    })
    text = await res.text()
  } catch (error) {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
    listeners.forEach((cleanup) => cleanup())
    if (options?.signal?.aborted) throw error
    if (timedOut) {
      throw new ApiError("请求在 12 秒内没有完成。请检查 VPN、Wi-Fi 或移动网络后重试。", {
        code: "REQUEST_TIMEOUT",
        status: 0,
        details: { path: "/system/runtime", timeoutMs },
      })
    }
    if (error instanceof TypeError) {
      throw new ApiError("网络连接已中断，暂时无法连接服务器。请检查 VPN、Wi-Fi 或移动网络后重试。", {
        code: "NETWORK_ERROR",
        status: 0,
        details: {
          path: "/system/runtime",
          cause: { name: error.name, message: error.message },
        },
      })
    }
    throw new ApiError("请求失败，请稍后重试。", {
      code: "REQUEST_FAILED",
      status: 0,
      details: {
        path: "/system/runtime",
        cause: error instanceof Error ? { name: error.name, message: error.message } : { message: String(error) },
      },
    })
  }

  if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
  listeners.forEach((cleanup) => cleanup())
  const raw = text.trim()
  if (!raw) {
    throw new ApiError(`Empty response body (status=${res.status})`, { code: "EMPTY_RESPONSE", status: res.status })
  }
  let json: unknown
  try {
    json = JSON.parse(text)
  } catch (e) {
    throw new ApiError(`Invalid JSON response (status=${res.status})`, {
      code: "INVALID_JSON",
      status: res.status,
      details: { cause: String(e), body: text.slice(0, 500) },
    })
  }
  const env = SystemRuntimeEnvelopeSchema.parse(json)
  return {
    ...env.data,
    ready: env.ok,
  }
}

export function getRelayMonitor(query?: RelayMonitorQuery, options?: ApiRequestExecutionOptions) {
  const search = buildRelayMonitorSearch(query)
  return apiRequest({
    path: `/system/relay-monitor${search}`,
    responseSchema: RelayMonitorSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getRelayDiagnosticsExportUrl(query?: RelayMonitorQuery) {
  return `${getBaseUrl()}/system/relay-diagnostics/export${buildRelayMonitorSearch(query)}`
}

export function getDesktopAgentRelease(currentVersion?: string | null, options?: ApiRequestExecutionOptions) {
  const search = currentVersion && currentVersion.trim() ? `?currentVersion=${encodeURIComponent(currentVersion.trim())}` : ""
  return apiRequest({
    path: `/system/desktop-agent-release${search}`,
    responseSchema: DesktopAgentReleaseSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getDesktopAgentSetupCatalog(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/desktop-agent/setup-catalog",
    responseSchema: DesktopAgentSetupCatalogSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function createDesktopAgentSetupSession(preferredProjectId?: string | null) {
  return apiRequest({
    path: "/system/desktop-agent/setup-sessions",
    method: "POST",
    body: {
      preferredProjectId: preferredProjectId && preferredProjectId.trim() ? preferredProjectId.trim() : null,
    },
    responseSchema: DesktopAgentSetupSessionSchema,
  })
}
