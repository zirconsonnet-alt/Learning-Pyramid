import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  acceptFriendRequest,
  cancelFriendRequest,
  createFriendRequest,
  deleteFriend,
  getFriendProfile,
  listFriendLeaderboard,
  listFriendRequests,
  listFriends,
  rejectFriendRequest,
} from "@/ui/api/friends"

async function invalidateFriendsData(qc: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    qc.invalidateQueries({ queryKey: ["friends", "list"] }),
    qc.invalidateQueries({ queryKey: ["friends", "requests"] }),
    qc.invalidateQueries({ queryKey: ["friends", "leaderboard"] }),
    qc.invalidateQueries({ queryKey: ["friends", "profile"] }),
  ])
}

export function useFriends(options?: { enabled?: boolean; limit?: number }) {
  const { enabled = true, limit } = options ?? {}
  return useQuery({
    queryKey: ["friends", "list", limit ?? "default"],
    queryFn: () => listFriends({ limit }),
    enabled,
    staleTime: 15_000,
  })
}

export function useFriendRequests(box: "incoming" | "outgoing" = "incoming", options?: { enabled?: boolean; limit?: number }) {
  const { enabled = true, limit } = options ?? {}
  const normalizedBox = box === "outgoing" ? "outgoing" : "incoming"
  return useQuery({
    queryKey: ["friends", "requests", normalizedBox, limit ?? "default"],
    queryFn: () => listFriendRequests({ box: normalizedBox, limit }),
    enabled,
    staleTime: 10_000,
  })
}

export function useFriendLeaderboard(enabled = true) {
  return useQuery({
    queryKey: ["friends", "leaderboard"],
    queryFn: listFriendLeaderboard,
    enabled,
    staleTime: 15_000,
  })
}

export function useFriendProfile(friendUserId?: string, enabled = true) {
  return useQuery({
    queryKey: ["friends", "profile", friendUserId ?? ""],
    queryFn: () => getFriendProfile(String(friendUserId)),
    enabled: enabled && Boolean(friendUserId),
    staleTime: 15_000,
  })
}

export function useCreateFriendRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createFriendRequest,
    onSuccess: async () => {
      await invalidateFriendsData(qc)
    },
  })
}

export function useAcceptFriendRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (requestId: string) => acceptFriendRequest(requestId),
    onSuccess: async () => {
      await invalidateFriendsData(qc)
    },
  })
}

export function useRejectFriendRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (requestId: string) => rejectFriendRequest(requestId),
    onSuccess: async () => {
      await invalidateFriendsData(qc)
    },
  })
}

export function useCancelFriendRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (requestId: string) => cancelFriendRequest(requestId),
    onSuccess: async () => {
      await invalidateFriendsData(qc)
    },
  })
}

export function useDeleteFriend() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (friendUserId: string) => deleteFriend(friendUserId),
    onSuccess: async () => {
      await invalidateFriendsData(qc)
    },
  })
}
