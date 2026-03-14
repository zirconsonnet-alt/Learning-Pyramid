import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const DesktopAgentSchema = z.object({
  agentId: z.string(),
  userId: z.string(),
  deviceName: z.string(),
  platform: z.string(),
  appVersion: z.string(),
  status: z.enum(["ONLINE", "OFFLINE"]),
  lastSeenAt: z.string(),
  pairedAt: z.string(),
})
export type DesktopAgent = z.infer<typeof DesktopAgentSchema>

const DesktopAgentListSchema = z.array(DesktopAgentSchema)
const PairingCodeSchema = z.object({
  pairingCode: z.string(),
  expiresAt: z.string(),
})

export function listDesktopAgents() {
  return apiRequest({
    path: "/desktop-agents",
    responseSchema: DesktopAgentListSchema,
  })
}

export function createDesktopAgentPairingCode() {
  return apiRequest({
    path: "/desktop-agents/pairing-codes",
    method: "POST",
    responseSchema: PairingCodeSchema,
  })
}
