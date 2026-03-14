import { useMutation, useQuery } from "@tanstack/react-query"

import {
  createDesktopAgentSetupSession,
  getDesktopAgentRelease,
  getDesktopAgentSetupCatalog,
  getRelayMonitor,
  getSystemCapabilities,
  getSystemRuntime,
} from "@/ui/api/system"
import type { RelayMonitorQuery } from "@/ui/api/system"

export function useSystemCapabilities() {
  return useQuery({
    queryKey: ["systemCapabilities"],
    queryFn: ({ signal }) => getSystemCapabilities({ signal }),
    staleTime: Infinity,
  })
}

export function useSystemRuntime(enabled = true) {
  return useQuery({
    queryKey: ["systemRuntime"],
    queryFn: ({ signal }) => getSystemRuntime({ signal }),
    enabled,
    staleTime: 2_000,
    refetchInterval: enabled ? 5_000 : false,
  })
}

export function useRelayMonitor(query?: RelayMonitorQuery, enabled = true) {
  return useQuery({
    queryKey: ["relayMonitor", query ?? {}],
    queryFn: ({ signal }) => getRelayMonitor(query, { signal }),
    enabled,
    staleTime: 2_000,
    refetchInterval: enabled ? 5_000 : false,
  })
}

export function useDesktopAgentRelease(currentVersion?: string | null, enabled = true) {
  return useQuery({
    queryKey: ["desktopAgentRelease", currentVersion ?? ""],
    queryFn: ({ signal }) => getDesktopAgentRelease(currentVersion, { signal }),
    enabled,
    staleTime: 30_000,
  })
}

export function useDesktopAgentSetupCatalog(enabled = true) {
  return useQuery({
    queryKey: ["desktopAgentSetupCatalog"],
    queryFn: ({ signal }) => getDesktopAgentSetupCatalog({ signal }),
    enabled,
    staleTime: 30_000,
  })
}

export function useCreateDesktopAgentSetupSession() {
  return useMutation({
    mutationFn: (preferredProjectId?: string | null) => createDesktopAgentSetupSession(preferredProjectId),
  })
}
