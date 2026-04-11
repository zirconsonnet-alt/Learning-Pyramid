import { useEffect, useMemo, useRef } from "react"

import type { SyncedLearningPlans } from "@/ui/api/profile"
import { useMyLearningPlans, useUpdateMyLearningPlans } from "@/ui/queries/profile"
import { learningPlansToSyncPayload, useLearningPlanStore } from "@/ui/store/learningPlanStore"

function learningPlansSyncKey(payload: SyncedLearningPlans) {
  return JSON.stringify(payload)
}

export function useLearningPlanRemoteSync(enabled: boolean, userId?: string | null) {
  const query = useMyLearningPlans(enabled && Boolean(userId))
  const { isPending: updateIsPending, mutate: updateLearningPlans } = useUpdateMyLearningPlans()
  const plansById = useLearningPlanStore((state) => state.plansById)
  const progressSnapshotsByPlanId = useLearningPlanStore((state) => state.progressSnapshotsByPlanId)
  const mergeSyncedLearningPlans = useLearningPlanStore((state) => state.mergeSyncedLearningPlans)
  const appliedRemoteRef = useRef("")
  const bootstrappedUserRef = useRef("")
  const lastRemotePayloadKeyRef = useRef("")
  const lastUploadedPayloadKeyRef = useRef("")
  const localPayload = useMemo(
    () => learningPlansToSyncPayload(plansById, progressSnapshotsByPlanId),
    [plansById, progressSnapshotsByPlanId],
  )
  const localPayloadKey = useMemo(() => learningPlansSyncKey(localPayload), [localPayload])
  const localPayloadRef = useRef(localPayload)

  useEffect(() => {
    localPayloadRef.current = localPayload
  }, [localPayload])

  useEffect(() => {
    if (!enabled || !userId) {
      appliedRemoteRef.current = ""
      bootstrappedUserRef.current = ""
      lastRemotePayloadKeyRef.current = ""
      lastUploadedPayloadKeyRef.current = ""
      return
    }
    if (!query.data) return
    const remotePayloadKey = learningPlansSyncKey(query.data)
    const applyKey = `${userId}:${remotePayloadKey}`
    if (appliedRemoteRef.current === applyKey) return
    mergeSyncedLearningPlans(query.data)
    appliedRemoteRef.current = applyKey
    bootstrappedUserRef.current = userId
    lastRemotePayloadKeyRef.current = remotePayloadKey
    if (lastUploadedPayloadKeyRef.current !== remotePayloadKey) {
      lastUploadedPayloadKeyRef.current = ""
    }
  }, [enabled, mergeSyncedLearningPlans, query.data, userId])

  useEffect(() => {
    if (!enabled || !userId) return
    if (bootstrappedUserRef.current !== userId) return
    if (query.isFetching || updateIsPending) return
    if (localPayloadKey === lastRemotePayloadKeyRef.current || localPayloadKey === lastUploadedPayloadKeyRef.current) return

    const timeoutId = globalThis.setTimeout(() => {
      const payload = localPayloadRef.current
      const payloadKey = learningPlansSyncKey(payload)
      if (payloadKey === lastRemotePayloadKeyRef.current || payloadKey === lastUploadedPayloadKeyRef.current) return
      lastUploadedPayloadKeyRef.current = payloadKey
      updateLearningPlans(payload, {
        onSuccess: (saved) => {
          const savedPayloadKey = learningPlansSyncKey(saved)
          lastRemotePayloadKeyRef.current = savedPayloadKey
          appliedRemoteRef.current = `${userId}:${savedPayloadKey}`
          mergeSyncedLearningPlans(saved)
        },
        onError: () => {
          if (lastUploadedPayloadKeyRef.current === payloadKey) {
            lastUploadedPayloadKeyRef.current = ""
          }
        },
      })
    }, 1500)

    return () => globalThis.clearTimeout(timeoutId)
  }, [enabled, localPayloadKey, mergeSyncedLearningPlans, query.isFetching, updateIsPending, updateLearningPlans, userId])

  return query
}
