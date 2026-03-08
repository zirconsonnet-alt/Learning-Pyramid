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

export function richContentToPlainText(rc: RichContent): string {
  return rc
    .map((b) => {
      if (b.kind === "TEXT") return b.text.trim()
      return `[IMAGE:${b.assetId}]`
    })
    .filter(Boolean)
    .join(" ")
}

