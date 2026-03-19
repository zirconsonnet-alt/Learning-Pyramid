import { z } from "zod"

const TextBlockSchema = z.object({
  kind: z.literal("TEXT"),
  text: z.string().min(1),
})

const ImageBlockSchema = z.object({
  kind: z.literal("IMAGE"),
  assetId: z.string().min(1),
})

export const ContentBlockSchema = z.discriminatedUnion("kind", [TextBlockSchema, ImageBlockSchema])
export type ContentBlock = z.infer<typeof ContentBlockSchema>

export const RichContentSchema = z.array(ContentBlockSchema).min(1)
export type RichContent = z.infer<typeof RichContentSchema>

export function richText(text: string): RichContent {
  return [{ kind: "TEXT", text }]
}

export function normalizeRichContent(rc: RichContent): RichContent {
  const next: RichContent = []
  for (const block of rc) {
    if (block.kind === "TEXT") {
      if (block.text.trim()) next.push({ kind: "TEXT", text: block.text })
      continue
    }
    if (block.assetId.trim()) next.push({ kind: "IMAGE", assetId: block.assetId })
  }
  return next
}

export function richContentText(rc: RichContent): string {
  return rc
    .filter((b): b is Extract<ContentBlock, { kind: "TEXT" }> => b.kind === "TEXT")
    .map((b) => b.text)
    .join("\n\n")
}

export function richContentImageAssetIds(rc: RichContent): string[] {
  return rc
    .filter((b): b is Extract<ContentBlock, { kind: "IMAGE" }> => b.kind === "IMAGE")
    .map((b) => b.assetId)
}

export function setRichContentText(rc: RichContent, text: string): RichContent {
  const next: RichContent = text.trim() ? [{ kind: "TEXT", text }] : []
  for (const assetId of richContentImageAssetIds(rc)) next.push({ kind: "IMAGE", assetId })
  return normalizeRichContent(next)
}

export function appendImageBlock(rc: RichContent, assetId: string): RichContent {
  return normalizeRichContent([
    ...rc.filter((block): block is Extract<ContentBlock, { kind: "TEXT" }> => block.kind === "TEXT"),
    ...richContentImageAssetIds(rc).map((id) => ({ kind: "IMAGE" as const, assetId: id })),
    { kind: "IMAGE", assetId },
  ])
}

export function removeImageBlockAt(rc: RichContent, imageIndex: number): RichContent {
  let currentIndex = -1
  return normalizeRichContent(
    rc.filter((block) => {
      if (block.kind !== "IMAGE") return true
      currentIndex += 1
      return currentIndex !== imageIndex
    }),
  )
}

export function richContentHasMeaning(rc: RichContent): boolean {
  return normalizeRichContent(rc).length > 0
}

export function richContentToPlainText(rc: RichContent): string {
  return rc
    .map((b) => {
      if (b.kind === "TEXT") return b.text.trim()
      return `[IMAGE:${b.assetId}]`
    })
    .filter(Boolean)
    .join(" ")
}
