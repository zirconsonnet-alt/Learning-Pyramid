import { useEffect, useRef, useState, type KeyboardEventHandler, type MutableRefObject, type Ref } from "react"
import { LoaderCircle, Trash2 } from "lucide-react"

import { uploadMediaAsset } from "@/ui/api/mediaAssets"
import { type RichContent, richContentImageAssetIds, richContentText } from "@/ui/api/richContent"
import { Button } from "@/ui/components/ui/button"
import { mediaAssetUrl } from "@/ui/api/mediaAssets"
import { cn } from "@/ui/utils"

type RichContentField = "question" | "answer"

type ReferenceCandidate = {
  recallPointId: string
  questionPreview: string
  answerPreview: string
}

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
  onUserActivity,
  referencePicker,
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
  onUserActivity?: () => void
  referencePicker?: {
    isOpen: boolean
    isLoading?: boolean
    query: string
    highlightedIndex: number
    candidates: ReferenceCandidate[]
    onQueryChange: (query: string) => void
    onHighlightChange: (index: number) => void
    onConfirm: () => void
    onSelect: (recallPointId: string) => void
    onClose: () => void
  }
}) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const localTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const referenceSearchRef = useRef<HTMLInputElement | null>(null)
  const text = richContentText(value)
  const imageAssetIds = richContentImageAssetIds(value)

  useEffect(() => {
    if (!referencePicker?.isOpen) return
    referenceSearchRef.current?.focus()
  }, [referencePicker?.isOpen])

  function setTextareaNode(node: HTMLTextAreaElement | null) {
    localTextareaRef.current = node
    if (!textareaRef) return
    if (typeof textareaRef === "function") {
      textareaRef(node)
      return
    }
    ;(textareaRef as MutableRefObject<HTMLTextAreaElement | null>).current = node
  }

  async function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    onUserActivity?.()
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
        ref={setTextareaNode}
        className={cn("min-h-[96px] w-full rounded-md border bg-background px-3 py-2 text-sm", textareaClassName)}
        value={text}
        onChange={(event) => {
          onUserActivity?.()
          onTextChange(event.target.value)
        }}
        onPaste={handlePaste}
        onKeyDown={(event) => {
          onUserActivity?.()
          onTextKeyDown?.(event)
        }}
        onFocus={() => onUserActivity?.()}
        onClick={() => onUserActivity?.()}
        disabled={disabled || isUploading}
        placeholder={placeholder}
      />
      {referencePicker?.isOpen ? (
        <div className="rounded-xl border border-primary/20 bg-[color:var(--theme-card-main-bg)] p-3 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.38)]">
          <div className="space-y-2">
            <input
              ref={referenceSearchRef}
              value={referencePicker.query}
              onChange={(event) => {
                onUserActivity?.()
                referencePicker.onQueryChange(event.target.value)
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault()
                  if (referencePicker.candidates.length > 0) {
                    referencePicker.onHighlightChange(
                      Math.min(referencePicker.highlightedIndex + 1, referencePicker.candidates.length - 1),
                    )
                  }
                  return
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault()
                  if (referencePicker.candidates.length > 0) {
                    referencePicker.onHighlightChange(Math.max(referencePicker.highlightedIndex - 1, 0))
                  }
                  return
                }
                if (event.key === "Tab" && event.shiftKey) {
                  event.preventDefault()
                  referencePicker.onClose()
                  localTextareaRef.current?.focus()
                  return
                }
                if ((event.key === "Tab" && !event.shiftKey) || event.key === "Enter") {
                  event.preventDefault()
                  referencePicker.onConfirm()
                  localTextareaRef.current?.focus()
                  return
                }
                if (event.key === "Escape") {
                  event.preventDefault()
                  referencePicker.onClose()
                  localTextareaRef.current?.focus()
                }
              }}
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
              placeholder="输入关键字筛选复述点，Tab 确认引用"
            />
            <div className="max-h-64 overflow-y-auto rounded-lg border border-border/60">
              {referencePicker.candidates.length > 0 ? (
                referencePicker.candidates.map((candidate, index) => {
                  const isHighlighted = index === referencePicker.highlightedIndex
                  return (
                    <button
                      key={candidate.recallPointId}
                      type="button"
                      className={cn(
                        "flex w-full flex-col items-start gap-1 border-b border-border/50 px-3 py-2.5 text-left text-sm last:border-b-0",
                        isHighlighted ? "bg-primary/10 text-foreground" : "bg-transparent text-foreground hover:bg-muted/40",
                      )}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        onUserActivity?.()
                        referencePicker.onSelect(candidate.recallPointId)
                        localTextareaRef.current?.focus()
                      }}
                    >
                      <div className="font-medium">{candidate.recallPointId}</div>
                      <div className="line-clamp-1 text-xs text-muted-foreground">问：{candidate.questionPreview}</div>
                      <div className="line-clamp-1 text-xs text-muted-foreground">答：{candidate.answerPreview}</div>
                    </button>
                  )
                })
              ) : referencePicker.isLoading ? (
                <div className="px-3 py-4 text-sm text-muted-foreground">正在搜索复述点...</div>
              ) : (
                <div className="px-3 py-4 text-sm text-muted-foreground">没有匹配的复述点，继续输入关键字试试。</div>
              )}
            </div>
          </div>
        </div>
      ) : null}
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
