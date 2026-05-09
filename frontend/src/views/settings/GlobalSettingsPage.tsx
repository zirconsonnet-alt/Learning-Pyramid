import { type CSSProperties } from "react"
import { Palette } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useCurrentUser } from "@/ui/queries/auth"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useMyLlmSettings, useUpdateMyGlobalSettings, useUpdateMyLlmSettings } from "@/ui/queries/profile"
import { useGlobalLlmSettings, useSystemCapabilities, useUpdateGlobalLlmSettings } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { usePomodoroStore } from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { THEME_PRESETS } from "@/ui/theme/themePresets"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
import { GlobalLlmSettingsCard, UserLlmSettingsCard } from "@/views/settings/components/LlmSettingsCards"
import { buildGlobalSettingsPath } from "@/views/settings/globalSettingsRouting"

const THEME_PRESET_ACTIVE_BORDER = "hsl(var(--primary) / 0.46)"
const THEME_PRESET_ACTIVE_RING = "0 0 0 1px hsl(var(--primary) / 0.42)"
const THEME_PRESET_ACTIVE_GLOW = "0 22px 40px -28px hsl(var(--primary) / 0.46)"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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

  usePageMeta({
    title: "全局配置 | LearningPyramid",
    description: "统一管理界面主题。番茄钟已经独立成固定功能页。",
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
  const membershipQ = useMembershipSummary(authEnabled)
  const llmSettingsMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const llmSettingsMemberReady = !authEnabled || !llmSettingsMemberBlocked

  async function persistGlobalSettings(overrides?: {
    theme?: string
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
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div data-guide-tour="ai-llm-check" onClick={() => completeGuideWalkthroughStep("ai-confirm-llm")}>
      {authEnabled ? (
        llmSettingsMemberReady ? (
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
          <MemberOnlyFeatureNotice
            title="大模型配置是会员专属功能"
            message="当前账号还没有有效会员。开通后就可以保存自己的 Base URL、模型名和 API Key。"
          />
        )
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
      </div>

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Palette className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>界面主题</CardTitle>
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

    </div>
  )
}
