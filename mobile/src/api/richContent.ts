import { z } from "zod"

const TextBlockSchema = z.object({
  kind: z.literal("TEXT"),
  text: z.string().min(1),
})

const ImageBlockSchema = z.object({
  kind: z.literal("IMAGE"),
  assetId: z.string().min(1),
})

export const RichContentSchema = z.array(z.discriminatedUnion("kind", [TextBlockSchema, ImageBlockSchema])).min(1)
export type RichContent = z.infer<typeof RichContentSchema>

export function normalizeRichContent(content: RichContent): RichContent {
  return content
    .map((block) => {
      if (block.kind === "TEXT") {
        const text = block.text.trim()
        return text ? { kind: "TEXT" as const, text } : null
      }
      const assetId = block.assetId.trim()
      return assetId ? { kind: "IMAGE" as const, assetId } : null
    })
    .filter((block): block is RichContent[number] => Boolean(block))
}

export function richText(text: string): RichContent {
  const trimmed = text.trim()
  return trimmed ? [{ kind: "TEXT", text: trimmed }] : []
}

export function richContentHasMeaning(content: RichContent) {
  return content.some((block) => {
    if (block.kind === "TEXT") return block.text.trim().length > 0
    return block.assetId.trim().length > 0
  })
}

export function setRichContentText(content: RichContent, text: string): RichContent {
  const trimmed = text.trim()
  const nonTextBlocks = content.filter((block) => block.kind !== "TEXT")
  return trimmed ? [{ kind: "TEXT", text: trimmed }, ...nonTextBlocks] : nonTextBlocks
}

export function richContentToPlainText(content: RichContent) {
  return content
    .map((block) => (block.kind === "TEXT" ? block.text.trim() : `[IMAGE:${block.assetId}]`))
    .filter(Boolean)
    .join(" ")
}
