import type { RichContent } from "@/ui/api/richContent"
import { mediaAssetUrl } from "@/ui/api/mediaAssets"

export function RichContentRenderer({
  projectId,
  value,
  className = "",
}: {
  projectId: string
  value: RichContent
  className?: string
}) {
  return (
    <div className={`space-y-3 ${className}`.trim()}>
      {value.map((block, index) => {
        if (block.kind === "TEXT") {
          return (
            <div key={`text-${index}`} className="whitespace-pre-wrap leading-6 text-foreground">
              {block.text}
            </div>
          )
        }
        return (
          <img
            key={`image-${index}-${block.assetId}`}
            src={mediaAssetUrl(projectId, block.assetId)}
            alt={`复述点图片 ${index + 1}`}
            className="max-h-72 rounded-xl border border-border/70 bg-muted/20 object-contain"
            loading="lazy"
          />
        )
      })}
    </div>
  )
}
