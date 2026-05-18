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

export function richContentToPlainText(content: RichContent) {
  return content
    .map((block) => (block.kind === "TEXT" ? block.text.trim() : `[IMAGE:${block.assetId}]`))
    .filter(Boolean)
    .join(" ")
}
