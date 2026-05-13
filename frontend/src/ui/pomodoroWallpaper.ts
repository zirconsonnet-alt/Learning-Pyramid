const POMODORO_WALLPAPER_DB_NAME = "learningpyramid-pomodoro-wallpaper"
const POMODORO_WALLPAPER_STORE_NAME = "wallpaper"
const POMODORO_WALLPAPER_RECORD_KEY = "current"
export const POMODORO_WALLPAPER_MAX_BYTES = 12 * 1024 * 1024

export type PomodoroWallpaperScope =
  | { kind: "local" }
  | { kind: "user"; userId: string }

type PomodoroWallpaperRecord = {
  blob: Blob
  name: string
  type: string
  updatedAt: number
}

export function resolvePomodoroWallpaperScope(
  authEnabled: boolean | undefined,
  userId: string | null | undefined,
): PomodoroWallpaperScope | null {
  if (authEnabled === undefined) return null
  if (!authEnabled) return { kind: "local" }
  return userId ? { kind: "user", userId } : null
}

export function getPomodoroWallpaperScopeSignature(scope: PomodoroWallpaperScope | null) {
  if (!scope) return ""
  return scope.kind === "user" ? `user:${scope.userId}` : "local"
}

function getPomodoroWallpaperRecordKey(scope: PomodoroWallpaperScope): IDBValidKey {
  if (scope.kind === "user") return ["user", scope.userId, POMODORO_WALLPAPER_RECORD_KEY]
  return POMODORO_WALLPAPER_RECORD_KEY
}

function openPomodoroWallpaperDatabase() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("当前浏览器不支持本地壁纸存储。"))
      return
    }
    const request = indexedDB.open(POMODORO_WALLPAPER_DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(POMODORO_WALLPAPER_STORE_NAME)) {
        db.createObjectStore(POMODORO_WALLPAPER_STORE_NAME)
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error("打开本地壁纸存储失败。"))
  })
}

async function runPomodoroWallpaperRequest<T>(
  mode: IDBTransactionMode,
  createRequest: (store: IDBObjectStore) => IDBRequest<T>,
) {
  const db = await openPomodoroWallpaperDatabase()
  return new Promise<T>((resolve, reject) => {
    let settled = false
    let requestResult: T | undefined
    const finish = (callback: () => void) => {
      if (settled) return
      settled = true
      db.close()
      callback()
    }
    const transaction = db.transaction(POMODORO_WALLPAPER_STORE_NAME, mode)
    const request = createRequest(transaction.objectStore(POMODORO_WALLPAPER_STORE_NAME))
    request.onsuccess = () => {
      requestResult = request.result
    }
    request.onerror = () => finish(() => reject(request.error ?? new Error("读写本地壁纸失败。")))
    transaction.oncomplete = () => finish(() => resolve(requestResult as T))
    transaction.onerror = () => finish(() => reject(transaction.error ?? new Error("读写本地壁纸失败。")))
    transaction.onabort = () => finish(() => reject(transaction.error ?? new Error("本地壁纸操作已取消。")))
  })
}

export async function readPomodoroWallpaperBlob(scope: PomodoroWallpaperScope) {
  const record = await runPomodoroWallpaperRequest<PomodoroWallpaperRecord | undefined>("readonly", (store) =>
    store.get(getPomodoroWallpaperRecordKey(scope)),
  )
  return record?.blob instanceof Blob ? record.blob : null
}

export async function savePomodoroWallpaperBlob(scope: PomodoroWallpaperScope, file: File) {
  const record: PomodoroWallpaperRecord = {
    blob: file,
    name: file.name,
    type: file.type,
    updatedAt: Date.now(),
  }
  await runPomodoroWallpaperRequest<IDBValidKey>("readwrite", (store) =>
    store.put(record, getPomodoroWallpaperRecordKey(scope)),
  )
}

export async function removePomodoroWallpaperBlob(scope: PomodoroWallpaperScope) {
  await runPomodoroWallpaperRequest<undefined>("readwrite", (store) =>
    store.delete(getPomodoroWallpaperRecordKey(scope)),
  )
}
