import { useEffect, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type {
  PromptAssemblyMode,
  UpdateUserAsrSettingsInput,
  UpdateUserLlmSettingsInput,
  UserAsrSettings,
  UserGlobalSettings,
  UserLlmSettings,
} from "../api/profile"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

type ThemeOption = {
  id: string
  label: string
}

const THEME_OPTIONS: ThemeOption[] = [
  { id: "light", label: "浅色" },
  { id: "dark", label: "深色" },
  { id: "system", label: "跟随系统" },
]

export function GlobalSettingsScreen({
  loading,
  errorMessage,
  llmSettings,
  asrSettings,
  globalSettings,
  saveLlmSettings,
  clearLlmApiKey,
  saveAsrSettings,
  clearAsrApiKey,
  saveTheme,
}: {
  loading: boolean
  errorMessage?: string | null
  llmSettings: UserLlmSettings | null
  asrSettings: UserAsrSettings | null
  globalSettings: Pick<UserGlobalSettings, "theme" | "updatedAt"> | null
  saveLlmSettings: (input: UpdateUserLlmSettingsInput) => void
  clearLlmApiKey: () => void
  saveAsrSettings: (input: UpdateUserAsrSettingsInput) => void
  clearAsrApiKey: () => void
  saveTheme: (theme: string) => void
}) {
  const [llmBaseUrl, setLlmBaseUrl] = useState("")
  const [llmModelName, setLlmModelName] = useState("")
  const [llmApiKey, setLlmApiKey] = useState("")
  const [promptAssemblyMode, setPromptAssemblyMode] = useState<PromptAssemblyMode>("system")
  const [asrBaseUrl, setAsrBaseUrl] = useState("")
  const [asrModelName, setAsrModelName] = useState("")
  const [asrApiKey, setAsrApiKey] = useState("")

  useEffect(() => {
    if (!llmSettings) return
    setLlmBaseUrl(llmSettings.baseUrl)
    setLlmModelName(llmSettings.modelName)
    setPromptAssemblyMode(llmSettings.promptAssemblyMode)
  }, [llmSettings])

  useEffect(() => {
    if (!asrSettings) return
    setAsrBaseUrl(asrSettings.baseUrl)
    setAsrModelName(asrSettings.modelName)
  }, [asrSettings])

  if (loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载中" />
      </Screen>
    )
  }

  if (errorMessage) {
    return (
      <Screen>
        <EmptyState title={errorMessage} />
      </Screen>
    )
  }

  return (
    <Screen>
      <Text style={styles.title}>全局设置</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>大模型</Text>
        <AppTextInput
          autoCapitalize="none"
          onChangeText={setLlmBaseUrl}
          placeholder="LLM Base URL"
          value={llmBaseUrl}
        />
        <AppTextInput onChangeText={setLlmModelName} placeholder="LLM 模型名" value={llmModelName} />
        <AppTextInput
          autoCapitalize="none"
          onChangeText={setLlmApiKey}
          placeholder="LLM API Key"
          secureTextEntry
          value={llmApiKey}
        />
        <View style={styles.typeRow}>
          <AppButton
            label="system"
            onPress={() => setPromptAssemblyMode("system")}
            style={styles.typeButton}
            variant={promptAssemblyMode === "system" ? "primary" : "secondary"}
          />
          <AppButton
            label="user_concat"
            onPress={() => setPromptAssemblyMode("user_concat")}
            style={styles.typeButton}
            variant={promptAssemblyMode === "user_concat" ? "primary" : "secondary"}
          />
        </View>
        {llmSettings?.savedApiKeyConfigured ? (
          <Text style={styles.meta}>已保存 {llmSettings.savedApiKeyPreview ?? ""}</Text>
        ) : null}
        <AppButton
          label="保存大模型"
          onPress={() => {
            const apiKey = llmApiKey.trim()
            saveLlmSettings({
              baseUrl: llmBaseUrl.trim(),
              modelName: llmModelName.trim(),
              ...(apiKey ? { apiKey } : {}),
              promptAssemblyMode,
            })
          }}
        />
        <AppButton label="清除大模型密钥" onPress={clearLlmApiKey} variant="secondary" />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>语音识别</Text>
        <AppTextInput
          autoCapitalize="none"
          onChangeText={setAsrBaseUrl}
          placeholder="ASR Base URL"
          value={asrBaseUrl}
        />
        <AppTextInput onChangeText={setAsrModelName} placeholder="ASR 模型名" value={asrModelName} />
        <AppTextInput
          autoCapitalize="none"
          onChangeText={setAsrApiKey}
          placeholder="ASR API Key"
          secureTextEntry
          value={asrApiKey}
        />
        {asrSettings?.savedApiKeyConfigured ? (
          <Text style={styles.meta}>已保存 {asrSettings.savedApiKeyPreview ?? ""}</Text>
        ) : null}
        <AppButton
          label="保存语音识别"
          onPress={() => {
            const apiKey = asrApiKey.trim()
            saveAsrSettings({
              baseUrl: asrBaseUrl.trim(),
              modelName: asrModelName.trim(),
              ...(apiKey ? { apiKey } : {}),
            })
          }}
        />
        <AppButton label="清除语音识别密钥" onPress={clearAsrApiKey} variant="secondary" />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>主题</Text>
        <View style={styles.themeList}>
          {THEME_OPTIONS.map((theme) => {
            const active = globalSettings?.theme === theme.id
            return (
              <Pressable
                accessibilityRole="button"
                key={theme.id}
                onPress={() => saveTheme(theme.id)}
                style={[styles.themeRow, active && styles.themeRowActive]}
              >
                <Text style={[styles.themeText, active && styles.themeTextActive]}>{theme.label}</Text>
              </Pressable>
            )
          })}
        </View>
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  section: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    gap: ui.spacing.md,
    paddingBottom: ui.spacing.xl,
  },
  sectionTitle: { color: ui.colors.text, fontSize: ui.type.sectionTitle, fontWeight: "800" },
  themeList: { gap: 0 },
  themeRow: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    paddingHorizontal: 2,
    paddingVertical: ui.spacing.xl,
  },
  themeRowActive: { backgroundColor: ui.colors.primarySoft },
  themeText: { color: ui.colors.text, fontSize: ui.type.body },
  themeTextActive: { color: "#1d4ed8", fontWeight: "800" },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
  typeButton: { flex: 1 },
  typeRow: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
})
