import { useQuery } from "@tanstack/react-query"

import { getSystemCapabilities, getSystemRuntime } from "@/ui/api/system"

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
