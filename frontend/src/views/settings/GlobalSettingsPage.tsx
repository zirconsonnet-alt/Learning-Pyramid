import { useState, type CSSProperties } from "react"
import { Clock3, Palette, RotateCcw, Save } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import { useMyLlmSettings, useUpdateMyGlobalSettings, useUpdateMyLlmSettings } from "@/ui/queries/profile"
import { useGlobalLlmSettings, useSystemCapabilities, useUpdateGlobalLlmSettings } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import {
  DEFAULT_PROJECT_REVIEW_TEMPLATE,
  cloneReviewChainTemplate,
  useGlobalConfigStore,
} from "@/ui/store/globalConfigStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { usePomodoroStore } from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { THEME_PRESETS } from "@/ui/theme/themePresets"
import { GlobalLlmSettingsCard, UserLlmSettingsCard } from "@/views/settings/components/LlmSettingsCards"
import { buildGlobalSettingsPath } from "@/views/settings/globalSettingsRouting"

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
}

let nextTemplateItemId = 1

const THEME_PRESET_ACTIVE_BORDER = "hsl(var(--primary) / 0.46)"
const THEME_PRESET_ACTIVE_RING = "0 0 0 1px hsl(var(--primary) / 0.42)"
const THEME_PRESET_ACTIVE_GLOW = "0 22px 40px -28px hsl(var(--primary) / 0.46)"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function createTemplateEditorItem(kind: "CONVERGENCE" | "REVIEW_TASK", count = 1): TemplateEditorItem {
  return { id: nextTemplateItemId++, kind, count: String(count) }
}

function toTemplateEditorItems(items: ReviewChainTemplateItem[]) {
  return items.map((item) => createTemplateEditorItem(item.kind, item.count ?? 1))
}

export function GlobalSettingsPage() {
  const selectedTheme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const transitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const defaultFocusPrompt = usePomodoroStore((state) => state.defaultFocusPrompt)
  const defaultBreakPrompt = usePomodoroStore((state) => state.defaultBreakPrompt)
  const microBreaks = usePomodoroStore((state) => state.microBreaks)
  const defaultProjectReviewTemplate = useGlobalConfigStore((state) => state.defaultProjectReviewTemplate)
  const setDefaultProjectReviewTemplate = useGlobalConfigStore((state) => state.setDefaultProjectReviewTemplate)
  const resetDefaultProjectReviewTemplate = useGlobalConfigStore((state) => state.resetDefaultProjectReviewTemplate)
  const [templateItems, setTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(defaultProjectReviewTemplate))
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [pendingTemplateKind, setPendingTemplateKind] = useState<"" | "CONVERGENCE" | "REVIEW_TASK">("")

  usePageMeta({
    title: "全局配置 | LearningPyramid",
    description: "统一管理界面主题和新建项目默认复习模板。番茄钟已经独立成固定功能页。",
    path: buildGlobalSettingsPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const globalLlmSettingsQ = useGlobalLlmSettings(capabilitiesQ.data !== undefined && !authEnabled)
  const updateGlobalLlmSettingsM = useUpdateGlobalLlmSettings()
  const myLlmSettingsQ = useMyLlmSettings(authEnabled)
  const updateMyLlmSettingsM = useUpdateMyLlmSettings()
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)

  async function persistGlobalSettings(overrides?: {
    theme?: string
    defaultProjectReviewTemplate?: ReviewChainTemplateItem[]
  }) {
    const payload = {
      theme: overrides?.theme ?? selectedTheme,
      pomodoro: {
        enabled,
        weeklySchedule,
        transitionSoundEnabled,
        defaultFocusPrompt,
        defaultBreakPrompt,
        microBreaks,
      },
      defaultProjectReviewTemplate: overrides?.defaultProjectReviewTemplate ?? defaultProjectReviewTemplate,
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  function buildTemplateDraft() {
    const items: ReviewChainTemplateItem[] = []
    let hasConvergence = false
    for (const item of templateItems) {
      if (item.kind === "CONVERGENCE") {
        items.push({ kind: "CONVERGENCE" })
        hasConvergence = true
        continue
      }
      const count = Number(item.count)
      if (!Number.isInteger(count) || count < 1) {
        setTemplateError("复习任务次数必须是大于等于 1 的整数")
        return null
      }
      items.push(count === 1 ? { kind: "REVIEW_TASK" } : { kind: "REVIEW_TASK", count })
    }
    if (items.length === 0) {
      setTemplateError("默认模板不能为空")
      return null
    }
    if (!hasConvergence) {
      setTemplateError("模板里至少需要一个收敛步骤")
      return null
    }
    return items
  }

  async function handleResetTemplate() {
    const defaultTemplate = cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)
    try {
      await persistGlobalSettings({ defaultProjectReviewTemplate: defaultTemplate })
      resetDefaultProjectReviewTemplate()
      setTemplateItems(toTemplateEditorItems(defaultTemplate))
      setTemplateError(null)
      showInfoFeedback("默认模板已恢复", "新建项目会重新使用系统默认的单步收敛模板。")
    } catch (err) {
      showErrorFeedback("恢复默认模板失败", formatApiError(err))
    }
  }

  function appendTemplateItem() {
    if (!pendingTemplateKind) return
    setTemplateItems((prev) => [...prev, createTemplateEditorItem(pendingTemplateKind)])
    setPendingTemplateKind("")
    if (templateError) setTemplateError(null)
  }

  async function saveDefaultReviewTemplate() {
    setTemplateError(null)
    const items = buildTemplateDraft()
    if (!items) return
    try {
      await persistGlobalSettings({ defaultProjectReviewTemplate: items })
      setDefaultProjectReviewTemplate(items)
      showSuccessFeedback("默认复习模板已保存", "之后新建的项目会自动套用这套模板，已有项目不会被强制改写。")
    } catch (err) {
      showErrorFeedback("保存默认复习模板失败", formatApiError(err))
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      {authEnabled ? (
        <UserLlmSettingsCard
          queryError={myLlmSettingsQ.error}
          saveError={updateMyLlmSettingsM.error}
          settings={myLlmSettingsQ.data}
          isLoading={myLlmSettingsQ.isLoading}
          isPending={updateMyLlmSettingsM.isPending}
          onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
            try {
              await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
              showSuccessFeedback("大模型密钥已清除", "当前账号会停止使用已保存密钥；未重新保存前，这个账号的大模型能力视为未接通。")
            } catch (err) {
              showErrorFeedback("清除大模型密钥失败", formatApiError(err))
            }
          }}
          onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
            try {
              await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
              showSuccessFeedback("大模型配置已保存", "当前账号之后在任意设备登录时都会复用这份大模型服务配置。")
            } catch (err) {
              showErrorFeedback("保存大模型配置失败", formatApiError(err))
            }
          }}
        />
      ) : (
        <GlobalLlmSettingsCard
          queryError={globalLlmSettingsQ.error}
          saveError={updateGlobalLlmSettingsM.error}
          settings={globalLlmSettingsQ.data}
          isLoading={globalLlmSettingsQ.isLoading}
          isPending={updateGlobalLlmSettingsM.isPending}
          onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
            try {
              await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
              showSuccessFeedback("大模型密钥已清除", "系统会停止使用已保存的全局密钥。")
            } catch (err) {
              showErrorFeedback("清除大模型密钥失败", formatApiError(err))
            }
          }}
          onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
            try {
              await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
              showSuccessFeedback("大模型配置已保存", "后端现在会通过已配置服务代理后续的大模型能力请求。")
            } catch (err) {
              showErrorFeedback("保存大模型配置失败", formatApiError(err))
            }
          }}
        />
      )}

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Palette className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>界面主题</CardTitle>
              <CardDescription className="mt-1">原本右上角的主题选择已经迁到这里。番茄钟则已经独立成固定功能页。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5 md:grid-cols-3">
          {THEME_PRESETS.map((theme) => {
            const isActive = selectedTheme === theme.id
            const previewCardStyle: CSSProperties = {
              background: theme.surface.background,
              borderColor: isActive ? THEME_PRESET_ACTIVE_BORDER : theme.surface.border,
              boxShadow: isActive ? `${THEME_PRESET_ACTIVE_RING}, ${THEME_PRESET_ACTIVE_GLOW}, ${theme.surface.shadow}` : theme.surface.shadow,
            }
            return (
              <button
                key={theme.id}
                type="button"
                className="flex w-full items-center justify-between gap-3 rounded-[1.4rem] border px-4 py-4 text-left transition-all duration-200 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
                style={previewCardStyle}
                disabled={updateGlobalSettings.isPending}
                onClick={async () => {
                  try {
                    await persistGlobalSettings({ theme: theme.id })
                    setTheme(theme.id)
                    showSuccessFeedback("主题已切换", `界面当前已切换为“${theme.label}”。`)
                  } catch (err) {
                    showErrorFeedback("切换主题失败", formatApiError(err))
                  }
                }}
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium" style={{ color: theme.surface.title }}>{theme.label}</div>
                  <div className="mt-0.5 text-xs" style={{ color: theme.surface.description }}>{theme.description}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    {theme.preview.map((color) => (
                      <span key={`${theme.id}-${color}`} className="h-4 w-4 rounded-full shadow-inner" style={{ backgroundColor: color, border: `1px solid ${theme.surface.swatchBorder}` }} />
                    ))}
                  </div>
                  {isActive ? (
                    <span className="theme-meta-strong font-semibold">当前</span>
                  ) : null}
                </div>
              </button>
            )
          })}
        </CardContent>
      </Card>

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Clock3 className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>新建项目默认复习模板</CardTitle>
              <CardDescription className="mt-1">这里定义之后新建项目的默认模板。已有项目还是在项目设置里单独维护自己的层配置。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background/90">
            {templateItems.length === 0 ? <div className="px-4 py-6 text-sm text-muted-foreground">还没有模板步骤，请在下方选择步骤类型后点击加号。</div> : null}

            {templateItems.map((item, index) => (
              <div key={item.id} className="border-t border-border/70 p-4 first:border-t-0">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex items-start gap-3">
                    <span className="theme-pill-default inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">第 {index + 1} 步</span>
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-foreground">{item.kind === "CONVERGENCE" ? "收敛" : "复习任务"}</div>
                      <div className="text-xs text-muted-foreground">{item.kind === "CONVERGENCE" ? "完成一轮后决定是否继续生成复习任务。" : "在当前范围上直接生成待执行复习任务。"}</div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                    {item.kind === "REVIEW_TASK" ? (
                      <div className="w-full max-w-[220px] space-y-2">
                        <Label htmlFor={`global-template-count-${item.id}`}>次数</Label>
                        <Input
                          id={`global-template-count-${item.id}`}
                          inputMode="numeric"
                          value={item.count}
                          onChange={(event) =>
                            setTemplateItems((prev) =>
                              prev.map((current) => (current.id === item.id ? { ...current, count: event.target.value } : current)),
                            )
                          }
                        />
                      </div>
                    ) : (
                      <div className="theme-pill-default rounded-full border px-3 py-1.5 text-xs font-medium">这个步骤没有额外参数</div>
                    )}

                    <Button type="button" variant="ghost" size="sm" onClick={() => setTemplateItems((prev) => prev.filter((current) => current.id !== item.id))}>
                      删除
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button type="button" variant="outline" size="icon" className="shrink-0" onClick={appendTemplateItem} disabled={!pendingTemplateKind} aria-label="追加模板步骤">
              <span className="text-lg leading-none">+</span>
            </Button>
            <div className="w-full sm:max-w-[220px]">
              <Label htmlFor="pendingGlobalTemplateKind" className="sr-only">选择步骤类型</Label>
              <select
                id="pendingGlobalTemplateKind"
                aria-label="选择步骤类型"
                className="h-10 w-full rounded-xl border bg-background px-4 text-sm"
                value={pendingTemplateKind}
                onChange={(event) => setPendingTemplateKind(event.target.value as "" | "CONVERGENCE" | "REVIEW_TASK")}
              >
                <option value="">选择类型</option>
                <option value="CONVERGENCE">收敛</option>
                <option value="REVIEW_TASK">复习任务</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={saveDefaultReviewTemplate} disabled={updateGlobalSettings.isPending}>
              <Save className="h-4 w-4" />
              保存默认模板
            </Button>
            <Button variant="outline" onClick={handleResetTemplate} disabled={updateGlobalSettings.isPending}>
              <RotateCcw className="h-4 w-4" />
              恢复系统默认
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setTemplateItems(toTemplateEditorItems(cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)))
                setTemplateError(null)
              }}
            >
              预览系统默认
            </Button>
          </div>

          {templateError ? <p className="text-sm text-destructive">{templateError}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}
