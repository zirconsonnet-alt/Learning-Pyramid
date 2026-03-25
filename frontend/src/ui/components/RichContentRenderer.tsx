import type { RichContent } from "@/ui/api/richContent"
import { mediaAssetUrl } from "@/ui/api/mediaAssets"

export function RichContentRenderer({
  projectId,
  value,
  className = "",
  textClassName = "whitespace-pre-wrap leading-6 text-foreground",
  imageClassName = "max-h-72 rounded-xl border border-border/70 bg-muted/20 object-contain",
}: {
  projectId: string
  value: RichContent
  className?: string
  textClassName?: string
  imageClassName?: string
}) {
  return (
    <div className={`space-y-3 ${className}`.trim()}>
      {value.map((block, index) => {
        if (block.kind === "TEXT") {
          return (
            <div key={`text-${index}`} className={textClassName}>
              {block.text}
            </div>
          )
        }
        return (
          <img
            key={`image-${index}-${block.assetId}`}
            src={mediaAssetUrl(projectId, block.assetId)}
            alt={`复述点图片 ${index + 1}`}
            className={imageClassName}
            loading="lazy"
          />
        )
      })}
    </div>
  )
}
