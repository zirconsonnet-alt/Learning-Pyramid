import { z } from "zod"

import { apiRequest, apiUrl } from "@/ui/api/http"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"

const IMAGE_UPLOAD_TARGET_BYTES = 900_000
const IMAGE_UPLOAD_MAX_DIMENSION = 1800
const IMAGE_PAYLOAD_TOO_LARGE_MESSAGE =
  "上传的图片过大，服务器或网关拒绝了这次请求。已尝试压缩图片；如果仍失败，请先裁剪或压缩后再粘贴。"

export const UploadedMediaAssetSchema = z.object({
  assetId: z.string(),
  mimeType: z.string().nullable().optional(),
  url: z.string(),
})

export type UploadedMediaAsset = z.infer<typeof UploadedMediaAssetSchema>

function canCompressImage(file: File) {
  const type = String(file.type || "").toLowerCase()
  return type.startsWith("image/") && type !== "image/gif" && file.size > IMAGE_UPLOAD_TARGET_BYTES
}

function loadImageFile(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error("图片读取失败"))
    }
    image.src = url
  })
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("图片压缩失败"))
          return
        }
        resolve(blob)
      },
      type,
      quality,
    )
  })
}

function compressedImageName(file: File) {
  const baseName = (file.name || "pasted-image").replace(/\.[^.]+$/, "").trim() || "pasted-image"
  return `${baseName}.jpg`
}

export async function prepareImageFileForUpload(file: File): Promise<File> {
  if (!canCompressImage(file) || typeof document === "undefined") return file

  try {
    const image = await loadImageFile(file)
    const sourceWidth = image.naturalWidth || image.width
    const sourceHeight = image.naturalHeight || image.height
    if (!sourceWidth || !sourceHeight) return file

    let bestBlob: Blob | null = null
    let maxDimension = IMAGE_UPLOAD_MAX_DIMENSION
    for (let pass = 0; pass < 3; pass += 1) {
      const scale = Math.min(1, maxDimension / Math.max(sourceWidth, sourceHeight))
      const width = Math.max(1, Math.round(sourceWidth * scale))
      const height = Math.max(1, Math.round(sourceHeight * scale))
      const canvas = document.createElement("canvas")
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext("2d")
      if (!ctx) return file
      ctx.drawImage(image, 0, 0, width, height)

      for (const quality of [0.82, 0.72, 0.62, 0.52]) {
        const blob = await canvasToBlob(canvas, "image/jpeg", quality)
        if (!bestBlob || blob.size < bestBlob.size) bestBlob = blob
        if (blob.size <= IMAGE_UPLOAD_TARGET_BYTES) {
          return new File([blob], compressedImageName(file), { type: "image/jpeg", lastModified: Date.now() })
        }
      }
      maxDimension = Math.max(900, Math.round(maxDimension * 0.75))
    }

    if (bestBlob && bestBlob.size < file.size) {
      return new File([bestBlob], compressedImageName(file), { type: "image/jpeg", lastModified: Date.now() })
    }
  } catch {
    return file
  }
  return file
}

export async function uploadMediaAsset(projectId: string, file: File) {
  if (isVirtualStudyReviewProjectId(projectId)) {
    return {
      assetId: `virtual-${Date.now()}`,
      mimeType: file.type || "image/jpeg",
      url: "",
    }
  }
  const uploadFile = await prepareImageFileForUpload(file)
  return apiRequest({
    path: `/projects/${projectId}/media-assets`,
    method: "POST",
    body: uploadFile,
    headers: {
      "Content-Type": uploadFile.type || "application/octet-stream",
      "X-Filename": encodeURIComponent(uploadFile.name || file.name || "image"),
    },
    responseSchema: UploadedMediaAssetSchema,
    payloadTooLargeMessage: IMAGE_PAYLOAD_TOO_LARGE_MESSAGE,
  })
}

export function mediaAssetUrl(projectId: string, assetId: string) {
  if (isVirtualStudyReviewProjectId(projectId)) {
    return ""
  }
  return apiUrl(`/projects/${projectId}/media-assets/${assetId}`)
}
