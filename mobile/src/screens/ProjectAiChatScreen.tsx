import { useMemo, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { LearningTaskNode } from "../api/learningTaskNodes"
import type { AskProjectLlmInput, SystemCapabilities } from "../api/system"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

type ChatContextKind = "object" | "task"
type ChatMessage = {
  content: string
  id: string
  role: "assistant" | "user"
}
type SelectableContext = {
  id: string
  kind: ChatContextKind
  title: string
}

const QUICK_PROMPTS = [
  { label: "生成自测", prompt: "请基于当前节点内容，为我生成一套自测题。先给题目，再统一给出答案和解析。" },
  { label: "梳理结构", prompt: "请基于当前节点内容，帮我梳理知识结构、重点和容易混淆的地方。" },
  { label: "帮我助记", prompt: "请基于当前节点内容，帮我设计几个助记方法。" },
] as const

export function ProjectAiChatScreen({
  activeLearningObjectNode,
  capabilities,
  capabilitiesErrorMessage,
  capabilitiesLoading,
  learningObjectNodes,
  learningTaskNodes,
  onAsk,
  openGlobalSettings,
}: {
  activeLearningObjectNode: LearningObjectNode | null
  capabilities: SystemCapabilities | null
  capabilitiesErrorMessage?: string | null
  capabilitiesLoading: boolean
  learningObjectNodes: LearningObjectNode[]
  learningTaskNodes: LearningTaskNode[]
  onAsk: (input: AskProjectLlmInput) => Promise<string>
  openGlobalSettings: () => void
}) {
  const objectContexts = useMemo(() => buildObjectContexts(learningObjectNodes), [learningObjectNodes])
  const taskContexts = useMemo(() => buildTaskContexts(learningTaskNodes), [learningTaskNodes])
  const preferredObjectId =
    activeLearningObjectNode?.kind === "leaf" ? activeLearningObjectNode.nodeId : objectContexts[0]?.id ?? null
  const [contextKind, setContextKind] = useState<ChatContextKind>(preferredObjectId ? "object" : "task")
  const [selectedObjectId, setSelectedObjectId] = useState<string | null>(preferredObjectId)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(taskContexts[0]?.id ?? null)
  const [composerValue, setComposerValue] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sending, setSending] = useState(false)
  const [localErrorMessage, setLocalErrorMessage] = useState<string | null>(null)
  const contexts = contextKind === "object" ? objectContexts : taskContexts
  const selectedContextId = contextKind === "object" ? selectedObjectId : selectedTaskId
  const selectedContext = contexts.find((item) => item.id === selectedContextId) ?? contexts[0] ?? null
  const llmConfigured = capabilities?.llmConfigured === true

  async function send() {
    const prompt = composerValue.trim()
    if (!prompt || !selectedContext || sending || !llmConfigured) return
    const userMessage: ChatMessage = { content: prompt, id: createLocalId(), role: "user" }
    setMessages((current) => [...current, userMessage])
    setComposerValue("")
    setLocalErrorMessage(null)
    setSending(true)
    try {
      const content = await onAsk({
        prompt,
        systemPrompt: buildSystemPrompt(contextKind, selectedContext.title),
        ...(contextKind === "object"
          ? { learningObjectNodeId: selectedContext.id }
          : { learningTaskNodeId: selectedContext.id }),
      })
      setMessages((current) => [...current, { content, id: createLocalId(), role: "assistant" }])
    } catch (error) {
      setLocalErrorMessage(error instanceof Error ? error.message : "AI 问答失败")
      setComposerValue(prompt)
    } finally {
      setSending(false)
    }
  }

  return (
    <Screen>
      <Text style={styles.title}>AI问答</Text>

      {capabilitiesLoading && !capabilities ? <LoadingState label="准备 AI 问答" /> : null}
      {capabilitiesErrorMessage ? <EmptyState title={capabilitiesErrorMessage} /> : null}
      {!capabilitiesLoading && capabilities && !llmConfigured ? (
        <View style={styles.section}>
          <EmptyState title="当前还没有接通可用的 LLM" />
          <AppButton label="全局设置" onPress={openGlobalSettings} variant="secondary" />
        </View>
      ) : null}

      {llmConfigured ? (
        <>
          <View style={styles.modeRow}>
            <ModeButton active={contextKind === "object"} label="学习对象" onPress={() => setContextKind("object")} />
            <ModeButton active={contextKind === "task"} label="学习任务" onPress={() => setContextKind("task")} />
          </View>

          {selectedContext ? (
            <View style={styles.contextList}>
              {contexts.slice(0, 12).map((item) => {
                const active = item.id === selectedContext.id
                return (
                  <Pressable
                    accessibilityRole="button"
                    key={item.id}
                    onPress={() => {
                      if (contextKind === "object") setSelectedObjectId(item.id)
                      else setSelectedTaskId(item.id)
                    }}
                    style={[styles.contextRow, active && styles.contextRowActive]}
                  >
                    <Text style={[styles.contextTitle, active && styles.contextTitleActive]} numberOfLines={1}>
                      {item.title}
                    </Text>
                  </Pressable>
                )
              })}
            </View>
          ) : (
            <EmptyState title="先选择一个节点开始提问" />
          )}

          <View style={styles.messages}>
            {messages.length === 0 && selectedContext ? (
              <Text style={styles.emptyPrompt}>当前上下文：{selectedContext.title}</Text>
            ) : null}
            {messages.map((message) => (
              <View key={message.id} style={[styles.message, message.role === "user" && styles.userMessage]}>
                <Text style={[styles.messageRole, message.role === "user" && styles.userMessageRole]}>
                  {message.role === "user" ? "你" : "AI"}
                </Text>
                <Text style={[styles.messageText, message.role === "user" && styles.userMessageText]}>
                  {message.content}
                </Text>
              </View>
            ))}
            {sending ? <Text style={styles.emptyPrompt}>正在思考...</Text> : null}
            {localErrorMessage ? <Text style={styles.errorText}>{localErrorMessage}</Text> : null}
          </View>

          <View style={styles.quickRow}>
            {QUICK_PROMPTS.map((item) => (
              <AppButton
                key={item.label}
                disabled={sending || !selectedContext}
                label={item.label}
                onPress={() => setComposerValue(item.prompt)}
                style={styles.quickButton}
                variant="secondary"
              />
            ))}
          </View>

          <View style={styles.composer}>
            <AppTextInput
              editable={!sending && Boolean(selectedContext)}
              multiline
              onChangeText={setComposerValue}
              placeholder="围绕当前节点提问"
              style={styles.composerInput}
              value={composerValue}
            />
            <AppButton
              disabled={sending || !composerValue.trim() || !selectedContext}
              label={sending ? "发送中" : "发送"}
              onPress={() => void send()}
            />
          </View>
        </>
      ) : null}
    </Screen>
  )
}

function buildObjectContexts(nodes: LearningObjectNode[]): SelectableContext[] {
  return nodes
    .filter((node) => node.kind === "leaf")
    .map((node) => ({
      id: node.nodeId,
      kind: "object" as const,
      title: node.title.trim() || "未命名内容",
    }))
}

function buildTaskContexts(nodes: LearningTaskNode[]): SelectableContext[] {
  return nodes.map((node) => ({
    id: node.nodeId,
    kind: "task" as const,
    title: node.title.trim() || (node.kind === "leaf" ? "未命名任务" : "未命名分组"),
  }))
}

function buildSystemPrompt(contextKind: ChatContextKind, title: string) {
  const kindLabel = contextKind === "object" ? "学习对象" : "学习任务"
  return [
    "请使用简体中文回答。",
    `当前问答围绕${kindLabel}“${title}”展开。`,
    "优先使用当前节点及项目上下文，不要编造项目内不存在的事实。",
  ].join(" ")
}

function createLocalId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function ModeButton({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[styles.modeButton, active && styles.modeButtonActive]}
    >
      <Text style={[styles.modeText, active && styles.modeTextActive]}>{label}</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  composer: { gap: ui.spacing.sm },
  composerInput: { minHeight: 116, textAlignVertical: "top" },
  contextList: { gap: ui.spacing.sm },
  contextRow: {
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    paddingHorizontal: ui.spacing.md,
    paddingVertical: ui.spacing.md,
  },
  contextRowActive: { backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  contextTitle: { color: ui.colors.text, fontSize: ui.type.control, fontWeight: "700" },
  contextTitleActive: { color: ui.colors.primaryText },
  emptyPrompt: { color: ui.colors.textMuted, fontSize: ui.type.control, lineHeight: 22, textAlign: "center" },
  errorText: { color: ui.colors.danger, fontSize: ui.type.control, lineHeight: 22 },
  message: {
    alignSelf: "flex-start",
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    gap: ui.spacing.xs,
    maxWidth: "92%",
    padding: ui.spacing.md,
  },
  messageRole: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "800" },
  messages: { gap: ui.spacing.md, minHeight: 120 },
  messageText: { color: ui.colors.text, fontSize: ui.type.body, lineHeight: 24 },
  modeButton: {
    alignItems: "center",
    borderColor: ui.colors.border,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    flex: 1,
    justifyContent: "center",
    minHeight: 40,
  },
  modeButtonActive: { backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  modeRow: { flexDirection: "row", gap: ui.spacing.sm },
  modeText: { color: ui.colors.textMuted, fontSize: ui.type.control, fontWeight: "700" },
  modeTextActive: { color: ui.colors.primaryText },
  quickButton: { flexGrow: 1, minWidth: 96 },
  quickRow: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
  section: { gap: ui.spacing.md },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
  userMessage: { alignSelf: "flex-end", backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  userMessageRole: { color: ui.colors.primaryText },
  userMessageText: { color: ui.colors.primaryText },
})
