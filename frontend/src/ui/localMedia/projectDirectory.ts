import { useEffect, useState } from "react"

export type DirectoryBindingPermission = "unsupported" | "missing" | "prompt" | "granted" | "denied"

type DirectoryRecord = {
  projectId: string
  handle: FileSystemDirectoryHandle
  savedAt: string
}

type GlobalDirectoryRecord = {
  key: string
  handle: FileSystemDirectoryHandle
  savedAt: string
}

export type ProjectDirectoryScanResult = {
  rootTitle: string
  relativeFilePaths: string[]
}

export type PomodoroRestMusicTrack = {
  name: string
  relativePath: string
}

export type PomodoroRestMusicScanResult = {
  rootTitle: string
  tracks: PomodoroRestMusicTrack[]
}

export type LocalDirectoryBindingState = {
  supported: boolean
  handleName: string | null
  permission: DirectoryBindingPermission
  loading: boolean
  error: string | null
}

export type ProjectDirectoryBindingState = LocalDirectoryBindingState
export type PomodoroRestMusicDirectoryBindingState = LocalDirectoryBindingState

const DB_NAME = "plm-local-media"
const DB_VERSION = 2
const PROJECT_DIRECTORY_STORE_NAME = "projectDirectories"
const GLOBAL_DIRECTORY_STORE_NAME = "globalDirectories"
const PROJECT_DIRECTORY_CHANGED_EVENT = "plm-project-directory-changed"
const POMODORO_REST_MUSIC_DIRECTORY_KEY = "pomodoro-rest-music"
const POMODORO_REST_MUSIC_DIRECTORY_CHANGED_EVENT = "plm-pomodoro-rest-music-directory-changed"
const IMPORTABLE_MEDIA_EXTENSIONS = new Set([".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"])
export const POMODORO_REST_MUSIC_EXTENSIONS = new Set([".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"])

function directoryPickerSupported() {
  return typeof window !== "undefined" && "showDirectoryPicker" in window && typeof indexedDB !== "undefined"
}

function currentScopedDirectoryKey(projectId: string) {
  if (typeof window === "undefined") return projectId
  const match = window.location.pathname.match(/^\/subjects\/([^/]+)\/projects\/([^/]+)/)
  if (!match) return projectId
  const subjectId = decodeURIComponent(match[1] ?? "")
  const currentScopedProjectId = decodeURIComponent(match[2] ?? "")
  if (!subjectId || currentScopedProjectId !== projectId) return projectId
  return `${subjectId}:${projectId}`
}

function directoryPickerId(projectKey: string) {
  return `plm-${projectKey.replace(/[^a-zA-Z0-9_-]/g, "-")}`.slice(0, 32)
}

function defaultState(): LocalDirectoryBindingState {
  return {
    supported: directoryPickerSupported(),
    handleName: null,
    permission: directoryPickerSupported() ? "missing" : "unsupported",
    loading: true,
    error: null,
  }
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(PROJECT_DIRECTORY_STORE_NAME)) {
        db.createObjectStore(PROJECT_DIRECTORY_STORE_NAME, { keyPath: "projectId" })
      }
      if (!db.objectStoreNames.contains(GLOBAL_DIRECTORY_STORE_NAME)) {
        db.createObjectStore(GLOBAL_DIRECTORY_STORE_NAME, { keyPath: "key" })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"))
  })
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(storeName, mode)
      const store = tx.objectStore(storeName)
      const req = fn(store)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error ?? new Error("IndexedDB request failed"))
    })
  } finally {
    db.close()
  }
}

async function loadDirectoryRecord(projectId: string): Promise<DirectoryRecord | null> {
  if (!directoryPickerSupported()) return null
  const record = await withStore<DirectoryRecord | undefined>(PROJECT_DIRECTORY_STORE_NAME, "readonly", (store) => store.get(projectId))
  return record ?? null
}

async function saveDirectoryRecord(projectId: string, handle: FileSystemDirectoryHandle): Promise<void> {
  await withStore<IDBValidKey>(PROJECT_DIRECTORY_STORE_NAME, "readwrite", (store) => store.put({ projectId, handle, savedAt: new Date().toISOString() } satisfies DirectoryRecord))
}

async function deleteDirectoryRecord(projectId: string): Promise<void> {
  await withStore<undefined>(PROJECT_DIRECTORY_STORE_NAME, "readwrite", (store) => store.delete(projectId))
}

async function loadGlobalDirectoryRecord(key: string): Promise<GlobalDirectoryRecord | null> {
  if (!directoryPickerSupported()) return null
  const record = await withStore<GlobalDirectoryRecord | undefined>(GLOBAL_DIRECTORY_STORE_NAME, "readonly", (store) => store.get(key))
  return record ?? null
}

async function saveGlobalDirectoryRecord(key: string, handle: FileSystemDirectoryHandle): Promise<void> {
  await withStore<IDBValidKey>(GLOBAL_DIRECTORY_STORE_NAME, "readwrite", (store) => store.put({ key, handle, savedAt: new Date().toISOString() } satisfies GlobalDirectoryRecord))
}

async function deleteGlobalDirectoryRecord(key: string): Promise<void> {
  await withStore<undefined>(GLOBAL_DIRECTORY_STORE_NAME, "readwrite", (store) => store.delete(key))
}

async function queryHandlePermission(handle: FileSystemDirectoryHandle): Promise<DirectoryBindingPermission> {
  try {
    const state = await handle.queryPermission({ mode: "read" })
    if (state === "granted") return "granted"
    if (state === "denied") return "denied"
    return "prompt"
  } catch {
    return "prompt"
  }
}

function permissionStateToBindingPermission(state: PermissionState): DirectoryBindingPermission {
  if (state === "granted") return "granted"
  if (state === "denied") return "denied"
  return "prompt"
}

async function loadBindingState(projectId: string): Promise<ProjectDirectoryBindingState> {
  if (!directoryPickerSupported()) {
    return {
      supported: false,
      handleName: null,
      permission: "unsupported",
      loading: false,
      error: null,
    }
  }
  try {
    const record = await loadDirectoryRecord(projectId)
    if (!record) {
      return {
        supported: true,
        handleName: null,
        permission: "missing",
        loading: false,
        error: null,
      }
    }
    return {
      supported: true,
      handleName: record.handle.name,
      permission: await queryHandlePermission(record.handle),
      loading: false,
      error: null,
    }
  } catch (err) {
    return {
      supported: true,
      handleName: null,
      permission: "missing",
      loading: false,
      error: err instanceof Error ? err.message : "读取本地目录绑定失败",
    }
  }
}

async function loadPomodoroRestMusicDirectoryState(): Promise<PomodoroRestMusicDirectoryBindingState> {
  if (!directoryPickerSupported()) {
    return {
      supported: false,
      handleName: null,
      permission: "unsupported",
      loading: false,
      error: null,
    }
  }
  try {
    const record = await loadGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY)
    if (!record) {
      return {
        supported: true,
        handleName: null,
        permission: "missing",
        loading: false,
        error: null,
      }
    }
    return {
      supported: true,
      handleName: record.handle.name,
      permission: await queryHandlePermission(record.handle),
      loading: false,
      error: null,
    }
  } catch (err) {
    return {
      supported: true,
      handleName: null,
      permission: "missing",
      loading: false,
      error: err instanceof Error ? err.message : "读取休息音乐目录绑定失败",
    }
  }
}

function notifyProjectDirectoryChanged(projectId: string) {
  window.dispatchEvent(new CustomEvent(PROJECT_DIRECTORY_CHANGED_EVENT, { detail: { projectId } }))
}

function notifyPomodoroRestMusicDirectoryChanged() {
  window.dispatchEvent(new CustomEvent(POMODORO_REST_MUSIC_DIRECTORY_CHANGED_EVENT))
}

function normalizeRelativeMaterialPath(materialId: string) {
  const normalized = String(materialId).replace(/\\/g, "/").trim()
  if (!normalized) return null
  if (normalized.startsWith("/")) return null
  if (/^[A-Za-z]:\//.test(normalized)) return null
  const parts = normalized.split("/").filter(Boolean)
  if (parts.length === 0) return null
  if (parts.some((part) => part === "." || part === "..")) return null
  return parts
}

export async function resolveProjectFile(projectId: string, materialId: string): Promise<File | null> {
  const record = await loadDirectoryRecord(currentScopedDirectoryKey(projectId))
  if (!record) return null
  const permission = await queryHandlePermission(record.handle)
  if (permission !== "granted") return null
  const parts = normalizeRelativeMaterialPath(materialId)
  if (!parts) return null

  let current = record.handle
  for (let index = 0; index < parts.length - 1; index += 1) {
    current = await current.getDirectoryHandle(parts[index])
  }
  const fileHandle = await current.getFileHandle(parts[parts.length - 1])
  return await fileHandle.getFile()
}

export async function resolveProjectSameStemSiblingFile(
  projectId: string,
  materialId: string,
  extensions: readonly string[],
): Promise<File | null> {
  const record = await loadDirectoryRecord(currentScopedDirectoryKey(projectId))
  if (!record) return null
  const permission = await queryHandlePermission(record.handle)
  if (permission !== "granted") return null
  const parts = normalizeRelativeMaterialPath(materialId)
  if (!parts) return null

  let current = record.handle
  for (let index = 0; index < parts.length - 1; index += 1) {
    current = await current.getDirectoryHandle(parts[index])
  }

  const materialName = parts[parts.length - 1]
  const dotIndex = materialName.lastIndexOf(".")
  const stem = (dotIndex >= 0 ? materialName.slice(0, dotIndex) : materialName).toLowerCase()
  if (!stem) return null

  const preferredOrder = new Map(
    extensions.map((ext, index) => [ext.startsWith(".") ? ext.toLowerCase() : `.${ext.toLowerCase()}`, index]),
  )
  let bestHandle: FileSystemFileHandle | null = null
  let bestRank = Number.POSITIVE_INFINITY

  for await (const [name, handle] of current.entries()) {
    if (handle.kind !== "file") continue
    const candidateDotIndex = name.lastIndexOf(".")
    const candidateStem = (candidateDotIndex >= 0 ? name.slice(0, candidateDotIndex) : name).toLowerCase()
    const candidateExt = candidateDotIndex >= 0 ? name.slice(candidateDotIndex).toLowerCase() : ""
    const rank = preferredOrder.get(candidateExt)
    if (rank === undefined || candidateStem !== stem) continue
    if (rank < bestRank) {
      bestRank = rank
      bestHandle = handle as FileSystemFileHandle
    }
  }

  return bestHandle ? await bestHandle.getFile() : null
}

export async function scanProjectDirectoryMedia(projectId: string): Promise<ProjectDirectoryScanResult> {
  const record = await loadDirectoryRecord(currentScopedDirectoryKey(projectId))
  if (!record) {
    throw new Error("当前项目还没有绑定本地素材目录。")
  }

  const permission = await queryHandlePermission(record.handle)
  if (permission !== "granted") {
    throw new Error("当前浏览器还没有授予目录读取权限，请先在项目设置里完成授权。")
  }

  const collected = new Set<string>()

  async function walk(dir: FileSystemDirectoryHandle, prefix: string[]) {
    for await (const [name, handle] of dir.entries()) {
      if (!name || name.startsWith(".")) continue
      if (handle.kind === "directory") {
        await walk(handle as FileSystemDirectoryHandle, [...prefix, name])
        continue
      }
      const dotIndex = name.lastIndexOf(".")
      const ext = dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : ""
      if (!IMPORTABLE_MEDIA_EXTENSIONS.has(ext)) continue
      collected.add([...prefix, name].join("/"))
    }
  }

  await walk(record.handle, [])

  return {
    rootTitle: record.handle.name || "已授权目录",
    relativeFilePaths: [...collected].sort((a, b) => a.localeCompare(b, "en")),
  }
}

export async function scanPomodoroRestMusicDirectory(): Promise<PomodoroRestMusicScanResult> {
  const record = await loadGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY)
  if (!record) {
    throw new Error("还没有绑定休息音乐目录。")
  }

  const permission = await queryHandlePermission(record.handle)
  if (permission !== "granted") {
    throw new Error("当前浏览器还没有授予休息音乐目录读取权限，请先在番茄钟设置里完成授权。")
  }

  const tracks: PomodoroRestMusicTrack[] = []

  async function walk(dir: FileSystemDirectoryHandle, prefix: string[]) {
    for await (const [name, handle] of dir.entries()) {
      if (!name || name.startsWith(".")) continue
      if (handle.kind === "directory") {
        await walk(handle as FileSystemDirectoryHandle, [...prefix, name])
        continue
      }
      const dotIndex = name.lastIndexOf(".")
      const ext = dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : ""
      if (!POMODORO_REST_MUSIC_EXTENSIONS.has(ext)) continue
      tracks.push({
        name,
        relativePath: [...prefix, name].join("/"),
      })
    }
  }

  await walk(record.handle, [])

  return {
    rootTitle: record.handle.name || "已授权音乐目录",
    tracks: tracks.sort((left, right) => left.relativePath.localeCompare(right.relativePath, "zh-CN")),
  }
}

export async function resolvePomodoroRestMusicFile(relativePath: string): Promise<File | null> {
  const record = await loadGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY)
  if (!record) return null
  const permission = await queryHandlePermission(record.handle)
  if (permission !== "granted") return null
  const parts = normalizeRelativeMaterialPath(relativePath)
  if (!parts) return null

  let current = record.handle
  for (let index = 0; index < parts.length - 1; index += 1) {
    current = await current.getDirectoryHandle(parts[index])
  }
  const fileHandle = await current.getFileHandle(parts[parts.length - 1])
  return await fileHandle.getFile()
}

export function useProjectDirectoryBinding(projectId: string) {
  const [state, setState] = useState<ProjectDirectoryBindingState>(defaultState)
  const projectKey = currentScopedDirectoryKey(projectId)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      if (!projectId) {
        setState({
          supported: directoryPickerSupported(),
          handleName: null,
          permission: directoryPickerSupported() ? "missing" : "unsupported",
          loading: false,
          error: null,
        })
        return
      }
      setState((prev) => ({ ...prev, loading: true, error: null }))
      const next = await loadBindingState(projectKey)
      if (!cancelled) {
        setState(next)
      }
    }

    void refresh()

    function onChanged(event: Event) {
      const detail = (event as CustomEvent<{ projectId?: string }>).detail
      if (!detail || detail.projectId === projectKey) {
        void refresh()
      }
    }

    window.addEventListener(PROJECT_DIRECTORY_CHANGED_EVENT, onChanged)
    return () => {
      cancelled = true
      window.removeEventListener(PROJECT_DIRECTORY_CHANGED_EVENT, onChanged)
    }
  }, [projectId, projectKey])

  async function authorizeDirectory(): Promise<DirectoryBindingPermission> {
    if (!directoryPickerSupported()) return "unsupported"
    if (!projectId) return "missing"
    const handle = await window.showDirectoryPicker({ id: directoryPickerId(projectKey), mode: "read" })
    await saveDirectoryRecord(projectKey, handle)
    notifyProjectDirectoryChanged(projectKey)
    return await queryHandlePermission(handle)
  }

  async function requestPermission(): Promise<DirectoryBindingPermission> {
    if (!projectId) return "missing"
    const record = await loadDirectoryRecord(projectKey)
    if (!record) return "missing"
    const state = await record.handle.requestPermission({ mode: "read" })
    notifyProjectDirectoryChanged(projectKey)
    return permissionStateToBindingPermission(state)
  }

  async function clearDirectory() {
    if (!projectId) return
    await deleteDirectoryRecord(projectKey)
    notifyProjectDirectoryChanged(projectKey)
  }

  return {
    ...state,
    authorizeDirectory,
    requestPermission,
    clearDirectory,
  }
}

export function usePomodoroRestMusicDirectoryBinding() {
  const [state, setState] = useState<PomodoroRestMusicDirectoryBindingState>(defaultState)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      setState((prev) => ({ ...prev, loading: true, error: null }))
      const next = await loadPomodoroRestMusicDirectoryState()
      if (!cancelled) {
        setState(next)
      }
    }

    void refresh()

    window.addEventListener(POMODORO_REST_MUSIC_DIRECTORY_CHANGED_EVENT, refresh)
    return () => {
      cancelled = true
      window.removeEventListener(POMODORO_REST_MUSIC_DIRECTORY_CHANGED_EVENT, refresh)
    }
  }, [])

  async function authorizeDirectory(): Promise<DirectoryBindingPermission> {
    if (!directoryPickerSupported()) return "unsupported"
    const handle = await window.showDirectoryPicker({ id: "plm-pomodoro-rest-music", mode: "read" })
    await saveGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY, handle)
    notifyPomodoroRestMusicDirectoryChanged()
    return await queryHandlePermission(handle)
  }

  async function requestPermission(): Promise<DirectoryBindingPermission> {
    const record = await loadGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY)
    if (!record) return "missing"
    const permission = await record.handle.requestPermission({ mode: "read" })
    notifyPomodoroRestMusicDirectoryChanged()
    return permissionStateToBindingPermission(permission)
  }

  async function clearDirectory() {
    await deleteGlobalDirectoryRecord(POMODORO_REST_MUSIC_DIRECTORY_KEY)
    notifyPomodoroRestMusicDirectoryChanged()
  }

  return {
    ...state,
    authorizeDirectory,
    requestPermission,
    clearDirectory,
  }
}
