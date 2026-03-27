import { useEffect } from "react"

type PageMetaInput = {
  title: string
  description: string
  path?: string
}

function ensureMeta(selector: string, create: () => HTMLMetaElement) {
  const existing = document.head.querySelector<HTMLMetaElement>(selector)
  if (existing) return existing
  const meta = create()
  document.head.append(meta)
  return meta
}

function ensureCanonical() {
  const existing = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (existing) return existing
  const link = document.createElement("link")
  link.rel = "canonical"
  document.head.append(link)
  return link
}

export function usePageMeta({ title, description, path }: PageMetaInput) {
  useEffect(() => {
    document.title = title

    const resolvedUrl = path ? new URL(path, window.location.origin).toString() : window.location.href
    ensureMeta('meta[name="description"]', () => {
      const meta = document.createElement("meta")
      meta.name = "description"
      return meta
    }).content = description

    ensureMeta('meta[property="og:title"]', () => {
      const meta = document.createElement("meta")
      meta.setAttribute("property", "og:title")
      return meta
    }).content = title

    ensureMeta('meta[property="og:description"]', () => {
      const meta = document.createElement("meta")
      meta.setAttribute("property", "og:description")
      return meta
    }).content = description

    ensureMeta('meta[property="og:url"]', () => {
      const meta = document.createElement("meta")
      meta.setAttribute("property", "og:url")
      return meta
    }).content = resolvedUrl

    ensureMeta('meta[name="twitter:title"]', () => {
      const meta = document.createElement("meta")
      meta.name = "twitter:title"
      return meta
    }).content = title

    ensureMeta('meta[name="twitter:description"]', () => {
      const meta = document.createElement("meta")
      meta.name = "twitter:description"
      return meta
    }).content = description

    ensureCanonical().href = resolvedUrl
  }, [description, path, title])
}
