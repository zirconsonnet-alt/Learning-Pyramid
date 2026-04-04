import type { CachedAsrSubtitleChunk } from "@/ui/store/asrStore"

const DB_NAME = "plm-browser-asr-subtitles"
const STORE_NAME = "chunks"
const DB_VERSION = 1
const MAX_CACHED_SUBTITLE_CHUNKS = 240

function indexedDbSupported() {
  return typeof indexedDB !== "undefined"
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "cacheKey" })
        store.createIndex("updatedAt", "updatedAt", { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"))
  })
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => void | Promise<T>): Promise<T> {
  if (!indexedDbSupported()) {
    throw new Error("当前浏览器不支持 IndexedDB。")
  }
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, mode)
      const store = tx.objectStore(STORE_NAME)
      let settled = false
      let result: T | undefined
      Promise.resolve(run(store))
        .then((value) => {
          result = value as T
        })
        .catch((error) => {
          if (settled) return
          settled = true
          reject(error)
          tx.abort()
        })
      tx.oncomplete = () => {
        if (settled) return
        settled = true
        resolve(result as T)
      }
      tx.onerror = () => {
        if (settled) return
        settled = true
        reject(tx.error ?? new Error("IndexedDB transaction failed"))
      }
      tx.onabort = () => {
        if (settled) return
        settled = true
        reject(tx.error ?? new Error("IndexedDB transaction aborted"))
      }
    })
  } finally {
    db.close()
  }
}

function getRequestResult<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error("IndexedDB request failed"))
  })
}

async function pruneOldEntries(store: IDBObjectStore) {
  const items = ((await getRequestResult(store.getAll())) as CachedAsrSubtitleChunk[])
    .filter((item) => item && item.cacheKey)
    .sort((left, right) => right.updatedAt - left.updatedAt)
  const extra = items.slice(MAX_CACHED_SUBTITLE_CHUNKS)
  await Promise.all(extra.map((item) => getRequestResult(store.delete(item.cacheKey))))
}

export async function getCachedAsrSubtitleChunk(cacheKey: string): Promise<CachedAsrSubtitleChunk | null> {
  if (!indexedDbSupported()) return null
  return await withStore<CachedAsrSubtitleChunk | null>("readonly", async (store) => {
    const value = await getRequestResult(store.get(cacheKey))
    return (value as CachedAsrSubtitleChunk | undefined) ?? null
  })
}

export async function upsertCachedAsrSubtitleChunk(payload: CachedAsrSubtitleChunk): Promise<void> {
  if (!indexedDbSupported()) return
  await withStore<void>("readwrite", async (store) => {
    await getRequestResult(
      store.put({
        ...payload,
        updatedAt: Date.now(),
      } satisfies CachedAsrSubtitleChunk),
    )
    await pruneOldEntries(store)
  })
}

export async function clearCachedAsrSubtitleChunks(): Promise<void> {
  if (!indexedDbSupported()) return
  await withStore<void>("readwrite", async (store) => {
    await getRequestResult(store.clear())
  })
}
