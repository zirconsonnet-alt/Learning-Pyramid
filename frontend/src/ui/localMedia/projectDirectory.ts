import { useEffect, useState } from "react"

type DirectoryBindingPermission = "unsupported" | "missing" | "prompt" | "granted" | "denied"

type DirectoryRecord = {
  projectId: string
  handle: FileSystemDirectoryHandle
  savedAt: string
}

export type ProjectDirectoryScanResult = {
  rootTitle: string
  relativeFilePaths: string[]
}

export type ProjectDirectoryBindingState = {
  supported: boolean
  handleName: string | null
  permission: DirectoryBindingPermission
  loading: boolean
  error: string | null
}

const DB_NAME = "plm-local-media"
const STORE_NAME = "projectDirectories"
const PROJECT_DIRECTORY_CHANGED_EVENT = "plm-project-directory-changed"
const IMPORTABLE_MEDIA_EXTENSIONS = new Set([".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"])

function directoryPickerSupported() {
  return typeof window !== "undefined" && "showDirectoryPicker" in window && typeof indexedDB !== "undefined"
}

function defaultState(): ProjectDirectoryBindingState {
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
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "projectId" })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"))
  })
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, mode)
      const store = tx.objectStore(STORE_NAME)
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
  const record = await withStore<DirectoryRecord | undefined>("readonly", (store) => store.get(projectId))
  return record ?? null
}

async function saveDirectoryRecord(projectId: string, handle: FileSystemDirectoryHandle): Promise<void> {
  await withStore<IDBValidKey>("readwrite", (store) => store.put({ projectId, handle, savedAt: new Date().toISOString() } satisfies DirectoryRecord))
}

async function deleteDirectoryRecord(projectId: string): Promise<void> {
  await withStore<undefined>("readwrite", (store) => store.delete(projectId))
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

function notifyProjectDirectoryChanged(projectId: string) {
  window.dispatchEvent(new CustomEvent(PROJECT_DIRECTORY_CHANGED_EVENT, { detail: { projectId } }))
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
  const record = await loadDirectoryRecord(projectId)
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

export async function scanProjectDirectoryMedia(projectId: string): Promise<ProjectDirectoryScanResult> {
  const record = await loadDirectoryRecord(projectId)
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

export function useProjectDirectoryBinding(projectId: string) {
  const [state, setState] = useState<ProjectDirectoryBindingState>(defaultState)

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
      const next = await loadBindingState(projectId)
      if (!cancelled) {
        setState(next)
      }
    }

    void refresh()

    function onChanged(event: Event) {
      const detail = (event as CustomEvent<{ projectId?: string }>).detail
      if (!detail || detail.projectId === projectId) {
        void refresh()
      }
    }

    window.addEventListener(PROJECT_DIRECTORY_CHANGED_EVENT, onChanged)
    return () => {
      cancelled = true
      window.removeEventListener(PROJECT_DIRECTORY_CHANGED_EVENT, onChanged)
    }
  }, [projectId])

  async function authorizeDirectory(): Promise<DirectoryBindingPermission> {
    if (!directoryPickerSupported()) return "unsupported"
    if (!projectId) return "missing"
    const handle = await window.showDirectoryPicker({ id: `plm-${projectId}`, mode: "read" })
    await saveDirectoryRecord(projectId, handle)
    notifyProjectDirectoryChanged(projectId)
    return await queryHandlePermission(handle)
  }

  async function requestPermission(): Promise<DirectoryBindingPermission> {
    if (!projectId) return "missing"
    const record = await loadDirectoryRecord(projectId)
    if (!record) return "missing"
    const state = await record.handle.requestPermission({ mode: "read" })
    notifyProjectDirectoryChanged(projectId)
    return permissionStateToBindingPermission(state)
  }

  async function clearDirectory() {
    if (!projectId) return
    await deleteDirectoryRecord(projectId)
    notifyProjectDirectoryChanged(projectId)
  }

  return {
    ...state,
    authorizeDirectory,
    requestPermission,
    clearDirectory,
  }
}
