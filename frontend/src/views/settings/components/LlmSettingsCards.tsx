import { useState } from "react"
import { Bot } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { cn } from "@/ui/utils"

export type LlmPromptAssemblyMode = "system" | "user_concat"

export type LlmSettingsSnapshot = {
  baseUrl: string
  modelName: string
  promptAssemblyMode: LlmPromptAssemblyMode
  savedApiKeyConfigured: boolean
  savedApiKeyPreview: string | null
  llmConfigured: boolean
  storyGenerationConfigured?: boolean
  llmSource: "user" | "global" | "env" | "none"
}

export type LlmSettingsSavePayload = {
  baseUrl: string
  modelName: string
  promptAssemblyMode: LlmPromptAssemblyMode
  apiKey?: string
}

export type LlmSettingsClearPayload = {
  baseUrl: string
  modelName: string
  promptAssemblyMode: LlmPromptAssemblyMode
}

const SAVED_API_KEY_MASK = "********"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function describeLlmSource(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "我的密钥"
  if (source === "global") return "全局密钥"
  if (source === "env") return "部署环境"
  return "未配置"
}

function describeLlmSourceTone(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "theme-pill-accent"
  if (source === "global") return "theme-pill-accent"
  if (source === "env") return "theme-pill-warm"
  return "theme-pill-default"
}

function getSettingsKey(settings: LlmSettingsSnapshot | undefined, title: string) {
  if (!settings) return `${title}:empty`
  return [
    title,
    settings.baseUrl,
    settings.modelName,
    settings.promptAssemblyMode,
    settings.savedApiKeyConfigured ? "key" : "no-key",
    settings.llmConfigured ? "ready" : "not-ready",
    settings.llmSource,
  ].join("|")
}

function PromptAssemblyModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: LlmPromptAssemblyMode
  onChange: (value: LlmPromptAssemblyMode) => void
  disabled: boolean
}) {
  const options: Array<{
    value: LlmPromptAssemblyMode
    title: string
    description: string
  }> = [
    {
      value: "system",
      title: "系统信息",
      description: "优先让兼容 OpenAI 的主流 chat 模型按 system/context 角色理解规则与上下文。",
    },
    {
      value: "user_concat",
      title: "拼接到用户信息",
      description: "把系统规则和节点上下文一并拼进用户消息，适合 qvq 这类对 system 遵循较弱的模型。",
    },
  ]

  return (
    <div className="grid gap-2 md:grid-cols-2">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-[1rem] border px-4 py-3 text-left transition",
              active
                ? "border-primary/35 bg-[hsl(var(--primary)/0.09)] shadow-[0_10px_30px_-22px_hsl(var(--primary)/0.55)]"
                : "border-border/70 bg-background hover:border-primary/25 hover:bg-[hsl(var(--primary)/0.04)]",
              disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-foreground">{option.title}</span>
              <span
                className={cn(
                  "inline-flex h-5 min-w-5 items-center justify-center rounded-full border px-1.5 text-[11px] font-semibold",
                  active ? "theme-pill-accent" : "theme-pill-default",
                )}
              >
                {active ? "当前" : "可选"}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{option.description}</p>
          </button>
        )
      })}
    </div>
  )
}

function SavedApiKeyInput({
  id,
  draftValue,
  onDraftChange,
  savedApiKeyConfigured,
  disabled,
  emptyPlaceholder,
  savedPlaceholder,
}: {
  id: string
  draftValue: string
  onDraftChange: (value: string) => void
  savedApiKeyConfigured: boolean
  disabled: boolean
  emptyPlaceholder: string
  savedPlaceholder: string
}) {
  const [isEditingSavedKey, setIsEditingSavedKey] = useState(false)
  const showSavedMask = savedApiKeyConfigured && !isEditingSavedKey && !draftValue.trim()

  return (
    <Input
      id={id}
      type="password"
      value={showSavedMask ? SAVED_API_KEY_MASK : draftValue}
      onFocus={() => {
        if (showSavedMask && !disabled) {
          setIsEditingSavedKey(true)
          onDraftChange("")
        }
      }}
      onBlur={() => {
        if (!draftValue.trim()) {
          setIsEditingSavedKey(false)
        }
      }}
      onChange={(event) => onDraftChange(event.target.value)}
      placeholder={savedApiKeyConfigured ? savedPlaceholder : emptyPlaceholder}
      disabled={disabled}
      autoComplete="off"
    />
  )
}

function LlmSettingsDraftForm({
  idPrefix,
  settings,
  isLoading,
  isPending,
  saveLabel,
  clearLabel,
  emptyApiKeyPlaceholder,
  savedApiKeyPlaceholder,
  onSave,
  onClearApiKey,
}: {
  idPrefix: string
  settings: LlmSettingsSnapshot | undefined
  isLoading: boolean
  isPending: boolean
  saveLabel: string
  clearLabel: string
  emptyApiKeyPlaceholder: string
  savedApiKeyPlaceholder: string
  onSave: (payload: LlmSettingsSavePayload) => Promise<void>
  onClearApiKey: (payload: LlmSettingsClearPayload) => Promise<void>
}) {
  const [baseUrlDraft, setBaseUrlDraft] = useState(settings?.baseUrl ?? "")
  const [modelDraft, setModelDraft] = useState(settings?.modelName ?? "")
  const [apiKeyDraft, setApiKeyDraft] = useState("")
  const [promptAssemblyModeDraft, setPromptAssemblyModeDraft] = useState<LlmPromptAssemblyMode>(
    settings?.promptAssemblyMode ?? "system",
  )

  const trimmedBaseUrl = baseUrlDraft.trim()
  const trimmedModel = modelDraft.trim()
  const trimmedApiKey = apiKeyDraft.trim()
  const canSave =
    !isLoading &&
    !isPending &&
    !!trimmedBaseUrl &&
    !!trimmedModel &&
    (
      trimmedBaseUrl !== (settings?.baseUrl ?? "") ||
      trimmedModel !== (settings?.modelName ?? "") ||
      promptAssemblyModeDraft !== (settings?.promptAssemblyMode ?? "system") ||
      !!trimmedApiKey
    )
  const canClearApiKey = !isLoading && !isPending && !!settings?.savedApiKeyConfigured

  return (
    <div className="space-y-3">
      <div className="grid gap-3">
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}BaseUrl`}>Base URL</Label>
          <Input
            id={`${idPrefix}BaseUrl`}
            value={baseUrlDraft}
            onChange={(event) => setBaseUrlDraft(event.target.value)}
            placeholder="https://api.openai.com/v1"
            disabled={isLoading || isPending}
            autoComplete="off"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}Model`}>模型名</Label>
          <Input
            id={`${idPrefix}Model`}
            value={modelDraft}
            onChange={(event) => setModelDraft(event.target.value)}
            placeholder="gpt-4o-mini"
            disabled={isLoading || isPending}
            autoComplete="off"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}ApiKey`}>API 密钥</Label>
          <SavedApiKeyInput
            id={`${idPrefix}ApiKey`}
            draftValue={apiKeyDraft}
            onDraftChange={setApiKeyDraft}
            savedApiKeyConfigured={!!settings?.savedApiKeyConfigured}
            emptyPlaceholder={emptyApiKeyPlaceholder}
            savedPlaceholder={savedApiKeyPlaceholder}
            disabled={isLoading || isPending}
          />
        </div>
        <div className="space-y-2">
          <Label>提示拼接模式</Label>
          <PromptAssemblyModeSelector
            value={promptAssemblyModeDraft}
            onChange={setPromptAssemblyModeDraft}
            disabled={isLoading || isPending}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={!canSave}
          onClick={() =>
            void onSave({
              baseUrl: trimmedBaseUrl,
              modelName: trimmedModel,
              promptAssemblyMode: promptAssemblyModeDraft,
              apiKey: trimmedApiKey || undefined,
            })
          }
        >
          {isPending ? "保存中..." : saveLabel}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!canClearApiKey}
          onClick={() =>
            void onClearApiKey({
              baseUrl: trimmedBaseUrl || settings?.baseUrl || "",
              modelName: trimmedModel || settings?.modelName || "",
              promptAssemblyMode: promptAssemblyModeDraft,
            })
          }
        >
          {clearLabel}
        </Button>
      </div>
    </div>
  )
}

function LlmSettingsCard({
  title,
  readyLabel,
  emptyLabel,
  saveLabel,
  clearLabel,
  idPrefix,
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  emptyApiKeyPlaceholder,
  savedApiKeyPlaceholder,
  onSave,
  onClearApiKey,
}: {
  title: string
  readyLabel: string
  emptyLabel: string
  saveLabel: string
  clearLabel: string
  idPrefix: string
  settings: LlmSettingsSnapshot | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  emptyApiKeyPlaceholder: string
  savedApiKeyPlaceholder: string
  onSave: (payload: LlmSettingsSavePayload) => Promise<void>
  onClearApiKey: (payload: LlmSettingsClearPayload) => Promise<void>
}) {
  return (
    <Card className="theme-card">
      <CardHeader className="theme-card-header">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Bot className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <CardTitle>{title}</CardTitle>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLlmSourceTone(settings?.llmSource ?? "none")}`}
            >
              {describeLlmSource(settings?.llmSource ?? "none")}
            </span>
            <span className="theme-meta px-3 py-1.5 text-xs">
              {settings?.llmConfigured ? readyLabel : emptyLabel}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <LlmSettingsDraftForm
          key={getSettingsKey(settings, title)}
          idPrefix={idPrefix}
          settings={settings}
          isLoading={isLoading}
          isPending={isPending}
          saveLabel={saveLabel}
          clearLabel={clearLabel}
          emptyApiKeyPlaceholder={emptyApiKeyPlaceholder}
          savedApiKeyPlaceholder={savedApiKeyPlaceholder}
          onSave={onSave}
          onClearApiKey={onClearApiKey}
        />

        {isLoading ? <p className="text-sm text-muted-foreground">加载{title}中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

export function GlobalLlmSettingsCard({
  title = "大模型配置",
  saveLabel = "保存大模型设置",
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  title?: string
  saveLabel?: string
  settings: LlmSettingsSnapshot | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: LlmSettingsSavePayload) => Promise<void>
  onClearApiKey: (payload: LlmSettingsClearPayload) => Promise<void>
}) {
  return (
    <LlmSettingsCard
      title={title}
      readyLabel="LLM 已可用"
      emptyLabel="LLM 未可用"
      saveLabel={saveLabel}
      clearLabel="清除已保存密钥"
      idPrefix="globalLlm"
      settings={settings}
      isLoading={isLoading}
      isPending={isPending}
      queryError={queryError}
      saveError={saveError}
      emptyApiKeyPlaceholder="输入新的 API Key"
      savedApiKeyPlaceholder="输入新的 API Key"
      onSave={onSave}
      onClearApiKey={onClearApiKey}
    />
  )
}

export function UserLlmSettingsCard({
  title = "大模型配置",
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  title?: string
  settings: LlmSettingsSnapshot | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: LlmSettingsSavePayload) => Promise<void>
  onClearApiKey: (payload: LlmSettingsClearPayload) => Promise<void>
}) {
  return (
    <LlmSettingsCard
      title={title}
      readyLabel="当前账号已就绪"
      emptyLabel="当前账号未配置"
      saveLabel="保存到我的账号"
      clearLabel="清除我的密钥"
      idPrefix="userLlm"
      settings={settings}
      isLoading={isLoading}
      isPending={isPending}
      queryError={queryError}
      saveError={saveError}
      emptyApiKeyPlaceholder="输入你的 API Key"
      savedApiKeyPlaceholder="输入你的 API Key"
      onSave={onSave}
      onClearApiKey={onClearApiKey}
    />
  )
}
