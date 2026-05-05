import { Download } from "lucide-react"

import { usePublicDownloads } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { ShowcaseFooter, ShowcaseSiteHeader } from "@/views/home/ShowcaseChrome"

const subtitleToolQuickGuide = [
  "下载后解压到任意本地目录，离线运行即可。",
  "选择视频根目录后，工具会直接在视频同目录生成同名 `.srt`。",
  "生成完成后无需移动文件，回到 LearningPyramid 重新打开视频即可读取字幕。",
] as const

const defaultIncludedComponents = ["ffmpeg", "whisper.cpp", "默认多语言模型"] as const
const defaultRequirements = ["Windows 10/11 x64"] as const

function formatDownloadSize(sizeBytes: number) {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return "大小待发布"
  const units = ["B", "KB", "MB", "GB"]
  let value = sizeBytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  const digits = value >= 100 || unitIndex === 0 ? 0 : value >= 10 ? 1 : 2
  return `${value.toFixed(digits)} ${units[unitIndex]}`
}

function formatPublishedAt(value: string | null | undefined) {
  if (!value) return "发布时间待同步"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(date)
}

export function SubtitleToolPage() {
  const publicDownloadsQ = usePublicDownloads()
  const recommendedDownload = publicDownloadsQ.data?.items.find((item) => item.recommended) ?? publicDownloadsQ.data?.items[0] ?? null
  const downloadNote = publicDownloadsQ.isError
    ? `接口报错：${publicDownloadsQ.error instanceof Error ? publicDownloadsQ.error.message : "请检查当前站点是否能访问 /api/system/public-downloads。"}`
    : !recommendedDownload && !publicDownloadsQ.isLoading
      ? publicDownloadsQ.data?.generatedAt
        ? "如果你已经完成打包，请确认 ZIP 文件已经跟着 catalog.json 一起放到服务端可读目录。"
        : "如果你是自托管部署，默认同步会跳过 public-downloads/。需要用 -IncludePublicDownloads 重新同步，或把 PLM_PUBLIC_DOWNLOADS_DIR 指到现有构建目录。"
      : ""
  const downloadFacts = [
    recommendedDownload?.version,
    recommendedDownload?.platform ?? (recommendedDownload ? "Windows x64" : null),
    recommendedDownload ? formatDownloadSize(recommendedDownload.sizeBytes) : null,
    recommendedDownload?.publishedAt ? `更新于 ${formatPublishedAt(recommendedDownload.publishedAt)}` : null,
  ].filter((item): item is string => Boolean(item))
  const includedComponents = recommendedDownload?.includedComponents.length
    ? recommendedDownload.includedComponents
    : [...defaultIncludedComponents]
  const requirements = recommendedDownload?.requirements.length ? recommendedDownload.requirements : [...defaultRequirements]

  usePageMeta({
    title: "LearningPyramid 字幕工具 | 离线批量生成字幕",
    description: "下载离线字幕工具，在本机批量生成同目录同名的 .srt 文件，再回到 LearningPyramid 直接使用。",
    path: "/subtitle-tool",
  })

  return (
    <div className="lp-showcase-page">
      <ShowcaseSiteHeader homeSectionPrefix="/" />

      <main id="top">
        <section className="lp-showcase-section lp-subtitle-tool-section">
          <div className="lp-showcase-container lp-subtitle-tool-shell">
            <article className="lp-subtitle-tool-card">
              <div className="lp-subtitle-tool-head">
                <h1>字幕工具</h1>
                <p>本机离线批量生成同目录同名 `.srt` 字幕。</p>
              </div>

              <div className="lp-subtitle-tool-actions">
                {recommendedDownload ? (
                  <a className="lp-showcase-btn lp-showcase-btn-primary" href={recommendedDownload.downloadPath}>
                    <Download className="h-4 w-4" />
                    下载 Windows 版
                  </a>
                ) : (
                  <span className="lp-showcase-btn lp-showcase-btn-secondary">构建包待发布</span>
                )}
                <a className="lp-subtitle-tool-inline-link" href="/#onboarding">
                  查看使用方式
                </a>
              </div>

              {downloadFacts.length ? (
                <div className="lp-subtitle-tool-meta" aria-label="构建信息">
                  {downloadFacts.map((item) => (
                    <span key={item} className="lp-subtitle-tool-chip">
                      {item}
                    </span>
                  ))}
                </div>
              ) : null}

              <p className="lp-subtitle-tool-flow">准备资源 → 选择目录 → 生成 → 回到 LearningPyramid</p>

              {downloadNote ? <div className="lp-subtitle-tool-note">{downloadNote}</div> : null}

              <div className="lp-subtitle-tool-disclosures">
                <details className="lp-subtitle-tool-disclosure">
                  <summary>使用说明</summary>
                  <div className="lp-subtitle-tool-disclosure-body">
                    <ul className="lp-subtitle-tool-list">
                      {subtitleToolQuickGuide.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </details>

                <details className="lp-subtitle-tool-disclosure">
                  <summary>使用方式</summary>
                  <div className="lp-subtitle-tool-disclosure-body">
                    <p>字幕工具本身就会直接把 `.srt` 生成在视频同目录同名位置，不需要你手动移动任何文件。</p>
                    <p>生成完成后，回到 LearningPyramid 重新打开视频，播放器就会按同目录同名规则自动读取这些字幕。</p>
                    <a className="lp-subtitle-tool-inline-link" href="/#onboarding">
                      查看首页使用方式
                    </a>
                  </div>
                </details>

                <details className="lp-subtitle-tool-disclosure">
                  <summary>技术细节</summary>
                  <div className="lp-subtitle-tool-disclosure-body">
                    <div className="lp-subtitle-tool-detail-block">
                      <strong>内置组件</strong>
                      <ul className="lp-subtitle-tool-list">
                        {includedComponents.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="lp-subtitle-tool-detail-block">
                      <strong>运行要求</strong>
                      <ul className="lp-subtitle-tool-list">
                        {requirements.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              </div>
            </article>
          </div>
        </section>
      </main>

      <ShowcaseFooter />
    </div>
  )
}
