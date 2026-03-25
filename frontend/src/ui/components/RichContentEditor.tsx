import { useState, type KeyboardEventHandler, type Ref } from "react"
import { LoaderCircle, Trash2 } from "lucide-react"

import { uploadMediaAsset } from "@/ui/api/mediaAssets"
import { type RichContent, richContentImageAssetIds, richContentText } from "@/ui/api/richContent"
import { Button } from "@/ui/components/ui/button"
import { mediaAssetUrl } from "@/ui/api/mediaAssets"
import { cn } from "@/ui/utils"

type RichContentField = "question" | "answer"

export function RichContentEditor({
  projectId,
  field,
  value,
  disabled = false,
  placeholder,
  onAppendImage,
  onRemoveImage,
  onTextChange,
  className,
  textareaClassName,
  imageClassName,
  textareaRef,
  onTextKeyDown,
}: {
  projectId: string
  field: RichContentField
  value: RichContent
  disabled?: boolean
  placeholder?: string
  onAppendImage: (assetId: string) => void
  onRemoveImage: (imageIndex: number) => void
  onTextChange: (text: string) => void
  className?: string
  textareaClassName?: string
  imageClassName?: string
  textareaRef?: Ref<HTMLTextAreaElement>
  onTextKeyDown?: KeyboardEventHandler<HTMLTextAreaElement>
}) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const text = richContentText(value)
  const imageAssetIds = richContentImageAssetIds(value)

  async function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    const items = Array.from(event.clipboardData.items ?? [])
    const imageFiles = items
      .filter((item) => item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file instanceof File)
    if (imageFiles.length === 0) return

    event.preventDefault()
    setUploadError(null)
    setIsUploading(true)
    try {
      for (const file of imageFiles) {
        const uploaded = await uploadMediaAsset(projectId, file)
        onAppendImage(uploaded.assetId)
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "图片粘贴失败")
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className={cn("space-y-3", className)}>
      <textarea
        ref={textareaRef}
        className={cn("min-h-[96px] w-full rounded-md border bg-background px-3 py-2 text-sm", textareaClassName)}
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        onPaste={handlePaste}
        onKeyDown={onTextKeyDown}
        disabled={disabled || isUploading}
        placeholder={placeholder}
      />
      {isUploading ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-primary">
          <span className="inline-flex items-center gap-1">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
            正在上传图片...
          </span>
        </div>
      ) : null}
      {imageAssetIds.length > 0 ? (
        <div className="flex flex-wrap gap-3">
          {imageAssetIds.map((assetId, imageIndex) => (
            <div key={`${assetId}-${imageIndex}`} className="space-y-2">
              <img
                src={mediaAssetUrl(projectId, assetId)}
                alt={`${field}-${imageIndex + 1}`}
                className={cn("h-28 w-28 rounded-xl border border-border/70 bg-muted/20 object-cover", imageClassName)}
                loading="lazy"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => onRemoveImage(imageIndex)}
                disabled={disabled || isUploading}
              >
                <Trash2 className="h-4 w-4" />
                删除图片
              </Button>
            </div>
          ))}
        </div>
      ) : null}
      {uploadError ? <p className="text-sm text-destructive">{uploadError}</p> : null}
    </div>
  )
}
