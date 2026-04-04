import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { AsrSegment, AsrTranscriptResult } from "@/ui/api/asr"

export type BrowserAsrServiceConfig = {
  baseUrl: string
  modelName: string
  apiKey: string
}

export type CachedAsrTranscript = {
  cacheKey: string
  projectId: string
  recallPointId: string
  sourceInstanceId: string
  provider: string
  centerMs: number
  preMs: number
  postMs: number
  segments: AsrSegment[]
  updatedAt: number
}

export type CachedAsrSubtitleChunk = {
  cacheKey: string
  projectId: string
  sourceInstanceId: string
  provider: string
  startMs: number
  endMs: number
  segments: AsrSegment[]
  updatedAt: number
}

type BrowserAsrState = {
  serviceConfig: BrowserAsrServiceConfig | null
  saveServiceConfig: (payload: BrowserAsrServiceConfig) => void
  clearServiceConfig: () => void
  reset: () => void
}

const initialState = {
  serviceConfig: null as BrowserAsrServiceConfig | null,
}

function trimServiceConfig(payload: BrowserAsrServiceConfig): BrowserAsrServiceConfig {
  return {
    baseUrl: payload.baseUrl.trim(),
    modelName: payload.modelName.trim(),
    apiKey: payload.apiKey.trim(),
  }
}

export function buildAsrTranscriptCacheKey(params: {
  projectId: string
  recallPointId: string
  sourceInstanceId: string
  provider: string
  centerMs: number
  preMs: number
  postMs: number
}) {
  return [
    params.projectId.trim(),
    params.recallPointId.trim(),
    params.sourceInstanceId.trim(),
    params.provider.trim().toUpperCase(),
    String(Math.floor(params.centerMs)),
    String(Math.floor(params.preMs)),
    String(Math.floor(params.postMs)),
  ].join("::")
}

export function isBrowserAsrConfigured(config: BrowserAsrServiceConfig | null | undefined) {
  return !!config?.baseUrl.trim() && !!config?.apiKey.trim()
}

export function buildAsrSubtitleChunkCacheKey(params: {
  projectId: string
  sourceInstanceId: string
  provider: string
  startMs: number
  endMs: number
}) {
  return [
    params.projectId.trim(),
    params.sourceInstanceId.trim(),
    params.provider.trim().toUpperCase(),
    String(Math.floor(params.startMs)),
    String(Math.floor(params.endMs)),
  ].join("::")
}

export function toCachedAsrTranscript(result: AsrTranscriptResult): CachedAsrTranscript {
  return {
    cacheKey: buildAsrTranscriptCacheKey({
      projectId: result.projectId,
      recallPointId: result.recallPointId,
      sourceInstanceId: result.sourceInstanceId,
      provider: result.provider,
      centerMs: result.centerMs,
      preMs: result.preMs,
      postMs: result.postMs,
    }),
    projectId: result.projectId,
    recallPointId: result.recallPointId,
    sourceInstanceId: result.sourceInstanceId,
    provider: result.provider,
    centerMs: result.centerMs,
    preMs: result.preMs,
    postMs: result.postMs,
    segments: result.segments,
    updatedAt: Date.now(),
  }
}

export function toCachedAsrSubtitleChunk(params: {
  projectId: string
  sourceInstanceId: string
  provider: string
  startMs: number
  endMs: number
  segments: AsrSegment[]
}): CachedAsrSubtitleChunk {
  return {
    cacheKey: buildAsrSubtitleChunkCacheKey({
      projectId: params.projectId,
      sourceInstanceId: params.sourceInstanceId,
      provider: params.provider,
      startMs: params.startMs,
      endMs: params.endMs,
    }),
    projectId: params.projectId,
    sourceInstanceId: params.sourceInstanceId,
    provider: params.provider,
    startMs: params.startMs,
    endMs: params.endMs,
    segments: params.segments,
    updatedAt: Date.now(),
  }
}

export const useAsrStore = create<BrowserAsrState>()(
  persist(
    (set) => ({
      ...initialState,
      saveServiceConfig: (payload) => set({ serviceConfig: trimServiceConfig(payload) }),
      clearServiceConfig: () => set((state) => ({ serviceConfig: state.serviceConfig ? { ...state.serviceConfig, apiKey: "" } : null })),
      reset: () => set(initialState),
    }),
    { name: "plm-browser-asr" },
  ),
)
