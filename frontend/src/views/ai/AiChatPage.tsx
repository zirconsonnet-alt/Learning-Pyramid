import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Copy,
  FileText,
  Folder,
  FolderOpen,
  Menu,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  PencilLine,
  RotateCcw,
  Search,
  Square,
  Sparkles,
  Trash2,
  Waypoints,
  Workflow,
} from "lucide-react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { Instance } from "@/ui/api/instances"
import { listLearningObjectNodes, listRecallPointsByLearningObjectNode, type LearningObjectNode } from "@/ui/api/learningObjects"
import { listLearningTaskNodes, listRecallPointsByLearningTaskNode, type LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { richContentToPlainText } from "@/ui/api/richContent"
import { getRecallPoint, type RecallPoint } from "@/ui/api/review"
import type { MaterialSourceKind } from "@/ui/api/projects"
import { askProjectLlmStream } from "@/ui/api/system"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { MarkdownRichText } from "@/ui/components/MarkdownRichText"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { formatRecallPointReference } from "@/ui/displayIdentifiers"
import { askCourseAgent } from "@/ui/llm/courseAgent"
import { useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useProjectMaterialSourceBinding } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { useInstances } from "@/ui/queries/workbench"
import { isSyntheticFilesContainer, sortLearningObjectNodeIdsForDisplay } from "@/ui/learningObjectDisplayOrder"
import { type AiChatConversation, type AiChatCourseEvidence, type AiChatMessage, useAiChatStore } from "@/ui/store/aiChatStore"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { createStudyPresenceTracker } from "@/ui/store/studyPresenceStore"
import { getLocalDateKey, touchDailyStudyActivity } from "@/ui/store/workbenchDailyStats"
import { syncStudyMetricsSnapshot } from "@/ui/studyMetricsSync"
import { buildSubtitleContextText, loadSubtitleDocumentForInstance } from "@/ui/subtitles/subtitleSupport"
import { cn } from "@/ui/utils"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"
import { buildAiChatPath, describeAiChatContextKind, isAiChatContextKind, type AiChatContextKind } from "@/views/ai/chatRouting"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
import { buildGlobalSettingsPath } from "@/views/settings/globalSettingsRouting"

type SidebarNode = {
  nodeId: string
  parentId: string | null
  title: string
  kind: "leaf" | "container"
  children: string[]
}

type SidebarTreeData = {
  nodeById: Record<string, SidebarNode>
  rootIds: string[]
}

type HistorySection = {
  label: string
  items: AiChatConversation[]
}

const QUICK_CHAT_ACTIONS = [
  {
    label: "生成自测",
    prompt: "请基于当前节点内容，为我生成一套自测题。先给题目，再在最后统一给出答案和解析。",
  },
  {
    label: "生成教案",
    prompt: "请基于当前节点内容，帮我生成一份简洁的教案提纲，包含教学目标、知识结构、讲解顺序、重点难点和结尾总结。",
  },
  {
    label: "帮我助记",
    prompt: "请基于当前节点内容，帮我设计几个助记方法，尽量包含关键词、联想、口诀、类比或记忆钩子。",
  },
] as const

const QA_ACTIVITY_WINDOW_MS = 30_000

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

async function copyText(text: string) {
  if (!text.trim()) return
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  throw new Error("当前环境不支持剪贴板写入")
}

function createMessage(
  role: AiChatMessage["role"],
  content: string,
  options?: { modelReliabilityIssue?: boolean; courseEvidence?: AiChatCourseEvidence[] },
): AiChatMessage {
  return {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    role,
    content,
    createdAt: Date.now(),
    modelReliabilityIssue: options?.modelReliabilityIssue,
    courseEvidence: options?.courseEvidence,
  }
}

function formatRelativeTime(ts: number) {
  const diff = Date.now() - ts
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour
  if (diff < minute) return "刚刚"
  if (diff < hour) return `${Math.max(1, Math.floor(diff / minute))} 分钟前`
  if (diff < day) return `${Math.max(1, Math.floor(diff / hour))} 小时前`
  return `${Math.max(1, Math.floor(diff / day))} 天前`
}

function groupConversationsByTime(conversations: AiChatConversation[]): HistorySection[] {
  const now = Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  const sections: HistorySection[] = [
    { label: "今天", items: [] },
    { label: "近 7 天", items: [] },
    { label: "更早", items: [] },
  ]

  for (const conversation of conversations) {
    const diff = now - conversation.updatedAt
    if (diff < dayMs) {
      sections[0].items.push(conversation)
      continue
    }
    if (diff < dayMs * 7) {
      sections[1].items.push(conversation)
      continue
    }
    sections[2].items.push(conversation)
  }

  return sections.filter((section) => section.items.length > 0)
}

function buildConversationPrompt(
  messages: AiChatMessage[],
  latestUserInput: string,
) {
  const recentBlocks: string[] = []
  let charBudget = 5_000

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === "system") continue
    const block = `${message.role === "user" ? "用户" : "助手"}：\n${message.content.trim()}`
    if (!block.trim()) continue
    if (recentBlocks.length > 0 && block.length > charBudget) break
    recentBlocks.unshift(block)
    charBudget -= block.length
  }

  const sections = recentBlocks.length > 0 ? ["以下是同一学习节点下的最近对话，请延续上下文回答最后一个用户问题。", ...recentBlocks] : []
  sections.push(`用户：\n${latestUserInput.trim()}`)
  return sections.join("\n\n")
}

function buildChatSystemPrompt(contextKind: AiChatContextKind, nodeLabel: string) {
  return [
    "请使用简体中文回答。",
    `当前问答围绕${describeAiChatContextKind(contextKind)}“${nodeLabel}”展开。`,
    "优先使用当前节点及项目上下文，不要编造项目内不存在的事实。",
    "如果需要给建议，尽量给出清晰、可执行的下一步。",
  ].join(" ")
}

function describeRecallPointTitle(recallPoint: RecallPoint | null, recallPointId: string | null) {
  const reference = formatRecallPointReference(recallPointId, "复述点待确认")
  if (!recallPoint) return reference
  const questionPreview = richContentToPlainText(recallPoint.question).trim()
  if (!questionPreview) return reference
  return `${reference} · ${questionPreview.length > 24 ? `${questionPreview.slice(0, 23).trimEnd()}…` : questionPreview}`
}

function normalizePreviewText(text: string, maxChars = 140) {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (!normalized) return ""
  if (normalized.length <= maxChars) return normalized
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`
}

function getRecallPointQuestionPreview(recallPoint: RecallPoint, maxChars = 120) {
  return normalizePreviewText(richContentToPlainText(recallPoint.question), maxChars)
}

function getRecallPointAnswerPreview(recallPoint: RecallPoint, maxChars = 140) {
  return normalizePreviewText(richContentToPlainText(recallPoint.answer), maxChars)
}

function responseLooksLikeMissingContext(content: string) {
  const normalized = content.replace(/\s+/g, "")
  if (!normalized) return false
  return (
    normalized.includes("当前节点内容缺失") ||
    normalized.includes("未提供当前节点的具体内容") ||
    normalized.includes("未提供当前节点内容") ||
    normalized.includes("请提供以下信息") ||
    normalized.includes("请补充以下信息") ||
    (normalized.includes("核心知识点") && normalized.includes("关键词列表"))
  )
}

function extractChineseNgrams(text: string, minLen = 2, maxLen = 4) {
  const normalized = text.replace(/\s+/g, "")
  const grams: string[] = []
  for (let size = minLen; size <= maxLen; size += 1) {
    if (normalized.length < size) continue
    for (let index = 0; index <= normalized.length - size; index += 1) {
      grams.push(normalized.slice(index, index + size))
    }
  }
  return grams
}

function extractContextKeywords(nodeLabel: string, recallPoints: RecallPoint[]) {
  const stopwords = new Set([
    "当前",
    "节点",
    "复述",
    "内容",
    "问题",
    "答案",
    "如何",
    "什么",
    "就是",
    "可以",
    "是否",
    "还有",
    "以及",
    "一个",
    "多个",
    "发生",
    "表示",
    "性质",
  ])
  const candidates = new Map<string, number>()
  const sourceTexts = [
    { text: nodeLabel, weight: 6 },
    ...recallPoints.slice(0, 8).flatMap((recallPoint) => [
      { text: getRecallPointQuestionPreview(recallPoint, 80), weight: 3 },
      { text: getRecallPointAnswerPreview(recallPoint, 120), weight: 2 },
    ]),
  ]

  for (const source of sourceTexts) {
    const chineseParts = source.text
      .replace(/\.mp4/gi, " ")
      .replace(/[0-9]+(?:\.[0-9]+)*/g, " ")
      .match(/[\u4e00-\u9fff]+/g)
    if (!chineseParts) continue
    for (const part of chineseParts) {
      if (part.length < 2) continue
      const grams = part.length <= 4 ? [part] : extractChineseNgrams(part, 2, Math.min(4, part.length))
      for (const gram of grams) {
        const keyword = gram.trim()
        if (keyword.length < 2 || stopwords.has(keyword)) continue
        candidates.set(keyword, (candidates.get(keyword) ?? 0) + source.weight)
      }
    }
  }

  return [...candidates.entries()]
    .sort((left, right) => right[1] - left[1] || right[0].length - left[0].length)
    .map(([keyword]) => keyword)
    .filter((keyword, index, items) => items.indexOf(keyword) === index)
    .slice(0, 24)
}

function responseLooksOffTopic(content: string, params: { nodeLabel: string; recallPoints: RecallPoint[] }) {
  const normalizedContent = content.replace(/\s+/g, "")
  if (!normalizedContent) return false

  const labelKeywords = extractContextKeywords(params.nodeLabel, [])
  const contextKeywords = extractContextKeywords(params.nodeLabel, params.recallPoints)
  if (contextKeywords.length === 0) return false

  const labelMatches = labelKeywords.filter((keyword) => normalizedContent.includes(keyword)).length
  const contextMatches = contextKeywords.filter((keyword) => normalizedContent.includes(keyword)).length

  return labelMatches === 0 && contextMatches < 2
}

function buildModelReliabilityGateMessage() {
  return "系统提示：已检测到当前模型连续两次未能可靠遵循当前节点内容，当前模型可能不适合这个任务。建议更换模型后再试。"
}

function countTrailingModelReliabilityIssues(messages: AiChatMessage[]) {
  let count = 0
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role !== "assistant") continue
    if (!message.modelReliabilityIssue) break
    count += 1
  }
  return count
}

function formatEvidenceTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

function parseAnchorPositionMs(position: string | null | undefined) {
  const match = String(position ?? "").trim().match(/^t=(\d+)$/)
  if (!match) return null
  const value = Number(match[1])
  return Number.isFinite(value) ? value : null
}

function getTaskSidebarChildIds(node: LearningTaskNode) {
  if (node.kind !== "container") return []
  return node.displayChildNodeIds ?? node.children
}

function buildTaskSidebarTree(nodes: LearningTaskNode[]): SidebarTreeData {
  const displayParentById: Record<string, string> = {}
  for (const node of nodes) {
    if (node.kind !== "container") continue
    for (const childId of getTaskSidebarChildIds(node)) {
      displayParentById[childId] = node.nodeId
    }
  }

  const nodeById: Record<string, SidebarNode> = {}
  for (const node of nodes) {
    nodeById[node.nodeId] = {
      nodeId: node.nodeId,
      parentId: displayParentById[node.nodeId] ?? node.parentId,
      title: formatLearningTaskNodeDisplayTitle(node.title),
      kind: node.kind,
      children: node.kind === "container" ? getTaskSidebarChildIds(node) : [],
    }
  }

  const rootIds = nodes
    .filter((node) => (displayParentById[node.nodeId] ?? node.parentId) === null)
    .map((node) => node.nodeId)
    .sort((left, right) => (nodeById[left]?.title ?? left).localeCompare(nodeById[right]?.title ?? right, "zh-Hans-CN", { numeric: true }))

  return { nodeById, rootIds }
}

function formatLearningObjectSidebarTitle(node: LearningObjectNode, depth: number) {
  const rawTitle = node.title.trim()
  if (!rawTitle && node.kind === "leaf") return "未命名内容"
  if (!rawTitle && node.kind === "container") return depth === 0 ? "学习对象根" : "未命名分组"
  if (depth === 0 && rawTitle === "Files") return "学习对象根"
  return rawTitle
}

function buildObjectSidebarTree(nodes: LearningObjectNode[]): SidebarTreeData {
  const syntheticFilesNodes = nodes.filter((node) => isSyntheticFilesContainer(node))
  const syntheticFilesIds = new Set(syntheticFilesNodes.map((node) => node.nodeId))
  const syntheticFilesById = Object.fromEntries(syntheticFilesNodes.map((node) => [node.nodeId, node])) as Record<string, LearningObjectNode>

  const normalizedNodes = nodes
    .filter((node) => !syntheticFilesIds.has(node.nodeId))
    .map((node) => {
      if (node.kind === "container") {
        return {
          ...node,
          children: node.children.flatMap((childId) => {
            if (!syntheticFilesIds.has(childId)) return [childId]
            const syntheticNode = syntheticFilesById[childId]
            return syntheticNode?.kind === "container" ? syntheticNode.children : []
          }),
        }
      }
      if (node.parentId && syntheticFilesIds.has(node.parentId)) {
        const syntheticParent = syntheticFilesById[node.parentId]
        return {
          ...node,
          parentId: syntheticParent?.parentId ?? null,
        }
      }
      return node
    })

  const rawNodeById: Record<string, LearningObjectNode> = {}
  for (const node of normalizedNodes) rawNodeById[node.nodeId] = node

  for (const node of normalizedNodes) {
    if (node.kind !== "container") continue
    rawNodeById[node.nodeId] = {
      ...node,
      children: sortLearningObjectNodeIdsForDisplay(node.children, rawNodeById),
    }
  }

  const depthById: Record<string, number> = {}
  function getDepth(nodeId: string): number {
    const cached = depthById[nodeId]
    if (cached !== undefined) return cached

    const node = rawNodeById[nodeId]
    if (!node || !node.parentId) {
      depthById[nodeId] = 0
      return 0
    }

    const depth = getDepth(node.parentId) + 1
    depthById[nodeId] = depth
    return depth
  }

  for (const node of normalizedNodes) getDepth(node.nodeId)

  const nodeById: Record<string, SidebarNode> = {}
  for (const node of normalizedNodes) {
    const normalizedNode = rawNodeById[node.nodeId]
    nodeById[node.nodeId] = {
      nodeId: node.nodeId,
      parentId: node.parentId,
      title: formatLearningObjectSidebarTitle(node, depthById[node.nodeId] ?? 0),
      kind: node.kind,
      children: node.kind === "container" && normalizedNode?.kind === "container" ? normalizedNode.children : [],
    }
  }

  const rootIds = sortLearningObjectNodeIdsForDisplay(
    normalizedNodes.filter((node) => node.parentId === null).map((node) => node.nodeId),
    rawNodeById,
  )

  return { nodeById, rootIds }
}

function collectAncestorIds(tree: SidebarTreeData, nodeId: string | null) {
  if (!nodeId) return [] as string[]
  const result: string[] = []
  let current = tree.nodeById[nodeId]
  while (current?.parentId) {
    result.unshift(current.parentId)
    current = tree.nodeById[current.parentId]
  }
  return result
}

function getNodeLabel(tree: SidebarTreeData, nodeId: string | null) {
  if (!nodeId) return "未选择节点"
  return tree.nodeById[nodeId]?.title ?? "未知节点"
}

function ChatRichText({ text, pendingAssistant = false }: { text: string; pendingAssistant?: boolean }) {
  if (!text.trim() && pendingAssistant) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-2 text-sm text-muted-foreground">
        <Sparkles className="h-4 w-4 text-primary" />
        正在思考...
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <MarkdownRichText text={text} />
      {pendingAssistant && text.trim() ? <span className="inline-block h-5 w-2 animate-pulse rounded-full bg-primary/35 align-[-0.15rem]" /> : null}
    </div>
  )
}

function SidebarTreeSection(props: {
  title: string
  icon: "task" | "object"
  tree: SidebarTreeData
  selectedNodeId: string | null
  expandedNodeIds: string[]
  disabled?: boolean
  embedded?: boolean
  onToggle: (nodeId: string) => void
  onSelect: (nodeId: string) => void
}) {
  const { title, icon, tree, selectedNodeId, expandedNodeIds, disabled, embedded, onToggle, onSelect } = props
  const SectionIcon = icon === "task" ? Waypoints : Workflow

  return (
    <section
      className={cn(
        embedded ? "" : "rounded-[1.5rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-3 shadow-[var(--theme-soft-shadow)]",
      )}
    >
      <div className="mb-3 flex items-center gap-2 px-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[color:var(--theme-soft-bg)] text-primary">
          <SectionIcon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{title}</div>
        </div>
      </div>

      {tree.rootIds.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--theme-soft-border)] px-4 py-5 text-sm text-muted-foreground">
          当前还没有可用节点。
        </div>
      ) : (
        <div className="space-y-1">
          {tree.rootIds.map((rootId) => (
            <SidebarTreeNodeRow
              key={rootId}
              nodeId={rootId}
              tree={tree}
              level={0}
              selectedNodeId={selectedNodeId}
              expandedNodeIds={expandedNodeIds}
              disabled={disabled}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function SidebarTreeNodeRow(props: {
  nodeId: string
  tree: SidebarTreeData
  level: number
  selectedNodeId: string | null
  expandedNodeIds: string[]
  disabled?: boolean
  onToggle: (nodeId: string) => void
  onSelect: (nodeId: string) => void
}) {
  const { nodeId, tree, level, selectedNodeId, expandedNodeIds, disabled, onToggle, onSelect } = props
  const node = tree.nodeById[nodeId]
  if (!node) return null

  const isContainer = node.kind === "container"
  const isExpanded = expandedNodeIds.includes(node.nodeId)
  const isSelected = selectedNodeId === node.nodeId
  const NodeIcon = isContainer ? (isExpanded ? FolderOpen : Folder) : FileText

  return (
    <div>
      <div className="flex items-center gap-1" style={{ paddingLeft: `${level * 14}px` }}>
        <button
          type="button"
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[color:var(--theme-subtle-text)] transition hover:bg-[color:var(--theme-soft-bg)] hover:text-foreground",
            !isContainer && "opacity-40",
          )}
          onClick={() => {
            if (!isContainer || disabled) return
            onToggle(node.nodeId)
          }}
          disabled={disabled || !isContainer}
          aria-label={isExpanded ? "收起节点" : "展开节点"}
        >
          {isContainer ? (isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />) : <span className="h-4 w-4" />}
        </button>
        <button
          type="button"
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2 rounded-2xl px-3 py-2 text-left transition",
            isSelected
              ? "bg-[hsl(var(--primary)/0.1)] text-foreground shadow-[0_18px_36px_-30px_hsl(var(--primary)/0.45)]"
              : "text-[color:var(--theme-subtle-text)] hover:bg-[color:var(--theme-soft-bg)] hover:text-foreground",
          )}
          onClick={() => {
            if (disabled) return
            onSelect(node.nodeId)
          }}
          disabled={disabled}
        >
          <NodeIcon className={cn("h-4 w-4 shrink-0", isSelected ? "text-primary" : "text-[color:var(--theme-subtle-text)]")} />
          <span className="min-w-0 truncate text-sm font-medium">{node.title}</span>
        </button>
      </div>

      {isContainer && isExpanded
        ? node.children.map((childNodeId) => (
            <SidebarTreeNodeRow
              key={childNodeId}
              nodeId={childNodeId}
              tree={tree}
              level={level + 1}
              selectedNodeId={selectedNodeId}
              expandedNodeIds={expandedNodeIds}
              disabled={disabled}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))
        : null}
    </div>
  )
}

function HistoryList(props: {
  conversations: AiChatConversation[]
  selectedConversationId: string | null
  searchValue: string
  disabled?: boolean
  embedded?: boolean
  resolveNodeLabel: (kind: AiChatContextKind, nodeId: string) => string
  onSearchChange: (value: string) => void
  onSelectConversation: (conversation: AiChatConversation) => void
  onRenameConversation: (conversation: AiChatConversation) => void
  onDeleteConversation: (conversation: AiChatConversation) => void
}) {
  const {
    conversations,
    selectedConversationId,
    searchValue,
    disabled,
    embedded,
    resolveNodeLabel,
    onSearchChange,
    onSelectConversation,
    onRenameConversation,
    onDeleteConversation,
  } = props

  const normalizedNeedle = searchValue.trim().toLowerCase()
  const filteredConversations = useMemo(() => {
    if (!normalizedNeedle) return conversations
    return conversations.filter((conversation) => {
      const haystack = `${conversation.title} ${resolveNodeLabel(conversation.contextKind, conversation.nodeId)} ${describeAiChatContextKind(conversation.contextKind)}`.toLowerCase()
      return haystack.includes(normalizedNeedle)
    })
  }, [conversations, normalizedNeedle, resolveNodeLabel])
  const historySections = useMemo(() => groupConversationsByTime(filteredConversations), [filteredConversations])

  return (
    <section
      className={cn(
        embedded ? "" : "rounded-[1.5rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-3 shadow-[var(--theme-soft-shadow)]",
      )}
    >
      {embedded ? (
        <div className="mb-3 flex items-center gap-2 px-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[color:var(--theme-soft-bg)] text-primary">
            <MessageSquarePlus className="h-4 w-4" />
          </div>
          <div className="text-sm font-semibold text-foreground">历史会话</div>
        </div>
      ) : null}
      <div className="relative mb-3">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--theme-subtle-text)]" />
        <Input
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索会话或节点"
          className="pl-9"
          disabled={disabled}
        />
      </div>

      {historySections.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[color:var(--theme-soft-border)] px-4 py-5 text-sm text-muted-foreground">
          {searchValue.trim() ? "没有匹配的历史会话。" : "还没有历史会话。"}
        </div>
      ) : (
        <div className="space-y-4">
          {historySections.map((section) => (
            <div key={section.label} className="space-y-2">
              <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">{section.label}</div>
              {section.items.map((conversation) => {
                const isActive = selectedConversationId === conversation.id
                return (
                  <div key={conversation.id} className="group relative">
                    <button
                      type="button"
                      className={cn(
                        "w-full rounded-2xl border px-3 py-3 pr-16 text-left transition",
                        isActive
                          ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] shadow-[0_18px_36px_-32px_hsl(var(--primary)/0.42)]"
                          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] hover:border-primary/15 hover:bg-[hsl(var(--primary)/0.04)]",
                      )}
                      onClick={() => {
                        if (disabled) return
                        onSelectConversation(conversation)
                      }}
                      disabled={disabled}
                    >
                      <div className="truncate text-sm font-semibold text-foreground">{conversation.title}</div>
                      <div className="mt-1 truncate text-xs text-muted-foreground">
                        {describeAiChatContextKind(conversation.contextKind)} · {resolveNodeLabel(conversation.contextKind, conversation.nodeId)}
                      </div>
                      <div className="mt-2 text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">
                        {formatRelativeTime(conversation.updatedAt)}
                      </div>
                    </button>

                    <div className="absolute right-2 top-2 flex items-center gap-1 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
                      <button
                        type="button"
                        className="flex h-8 w-8 items-center justify-center rounded-xl text-[color:var(--theme-subtle-text)] transition hover:bg-[color:var(--theme-soft-bg)] hover:text-foreground"
                        onClick={(event) => {
                          event.stopPropagation()
                          if (disabled) return
                          onRenameConversation(conversation)
                        }}
                        disabled={disabled}
                        aria-label="重命名会话"
                      >
                        <PencilLine className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        className="flex h-8 w-8 items-center justify-center rounded-xl text-[color:var(--theme-subtle-text)] transition hover:bg-destructive/10 hover:text-destructive"
                        onClick={(event) => {
                          event.stopPropagation()
                          if (disabled) return
                          onDeleteConversation(conversation)
                        }}
                        disabled={disabled}
                        aria-label="删除会话"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SidebarManagementBar(props: {
  disabled?: boolean
  canCollapse?: boolean
  onCollapse?: () => void
  onNewConversation: () => void
}) {
  const { disabled, canCollapse, onCollapse, onNewConversation } = props

  return (
    <div className="flex items-center justify-between gap-3">
      <div className="pl-1 text-sm font-semibold text-foreground">会话管理</div>
      <div className="inline-flex items-center rounded-full border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-1">
        {canCollapse && onCollapse ? (
          <>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full"
              onClick={onCollapse}
              aria-label="收起左侧栏"
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
            <div className="mx-1 h-5 w-px bg-[color:var(--theme-soft-border)]" />
          </>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="rounded-full px-3"
          onClick={onNewConversation}
          disabled={disabled}
        >
          <MessageSquarePlus className="h-4 w-4" />
          新会话
        </Button>
      </div>
    </div>
  )
}

function SidebarPanel(props: {
  activeKind: AiChatContextKind
  activeTree: SidebarTreeData | null
  activeNodeId: string | null
  expandedNodeIds: string[]
  isStreaming: boolean
  conversations: AiChatConversation[]
  selectedConversationId: string | null
  searchValue: string
  resolveNodeLabel: (kind: AiChatContextKind, nodeId: string) => string
  onToggleNode: (nodeId: string) => void
  onSelectNode: (nodeId: string) => void
  onSearchChange: (value: string) => void
  onNewConversation: () => void
  onSelectConversation: (conversation: AiChatConversation) => void
  onRenameConversation: (conversation: AiChatConversation) => void
  onDeleteConversation: (conversation: AiChatConversation) => void
  canCollapseSidebar?: boolean
  onCollapseSidebar?: () => void
}) {
  const {
    activeKind,
    activeTree,
    activeNodeId,
    expandedNodeIds,
    isStreaming,
    conversations,
    selectedConversationId,
    searchValue,
    resolveNodeLabel,
    onToggleNode,
    onSelectNode,
    onSearchChange,
    onNewConversation,
    onSelectConversation,
    onRenameConversation,
    onDeleteConversation,
    canCollapseSidebar,
    onCollapseSidebar,
  } = props

  return (
    <section className="overflow-hidden rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] shadow-[var(--theme-soft-shadow)]">
      <div className="px-4 py-4">
        <SidebarManagementBar
          disabled={isStreaming || !activeNodeId}
          canCollapse={canCollapseSidebar}
          onCollapse={onCollapseSidebar}
          onNewConversation={onNewConversation}
        />
      </div>

      <div className="border-t border-[color:var(--theme-soft-border)] px-4 py-4">
        {activeTree ? (
          <SidebarTreeSection
            title={activeKind === "task" ? "学习任务节点" : "学习对象节点"}
            icon={activeKind === "task" ? "task" : "object"}
            tree={activeTree}
            selectedNodeId={activeNodeId}
            expandedNodeIds={expandedNodeIds}
            disabled={isStreaming}
            embedded
            onToggle={onToggleNode}
            onSelect={onSelectNode}
          />
        ) : null}
      </div>

      <div className="border-t border-[color:var(--theme-soft-border)] px-4 py-4">
        <HistoryList
          conversations={conversations}
          selectedConversationId={selectedConversationId}
          searchValue={searchValue}
          disabled={isStreaming}
          embedded
          resolveNodeLabel={resolveNodeLabel}
          onSearchChange={onSearchChange}
          onSelectConversation={onSelectConversation}
          onRenameConversation={onRenameConversation}
          onDeleteConversation={onDeleteConversation}
        />
      </div>
    </section>
  )
}

function ChatMessageRow(props: {
  message: AiChatMessage
  pendingAssistant?: boolean
  showActions?: boolean
  onCopy?: (content: string) => void
  onRegenerate?: () => void
  onJumpEvidence?: (evidence: AiChatCourseEvidence) => void
}) {
  const { message, pendingAssistant, showActions, onCopy, onRegenerate, onJumpEvidence } = props

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[min(100%,46rem)] rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-5 py-4 text-[15px] leading-7 text-foreground shadow-[var(--theme-soft-shadow)]">
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
      </div>
    )
  }

  if (message.role === "system") {
    return (
      <div className="flex justify-center">
        <div className="max-w-[min(100%,46rem)] rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-[14px] leading-7 text-amber-900 shadow-[var(--theme-soft-shadow)]">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">系统提示</div>
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,hsl(var(--primary)),hsl(var(--primary)/0.72))] text-primary-foreground shadow-[0_18px_34px_-24px_hsl(var(--primary)/0.55)]">
        <Bot className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 pt-1">
        <ChatRichText text={message.content} pendingAssistant={pendingAssistant} />
        {message.courseEvidence && message.courseEvidence.length > 0 ? (
          <div className="mt-4 space-y-2">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">依据片段</div>
            <div className="grid gap-2">
              {message.courseEvidence.map((evidence, index) => (
                <button
                  key={`${evidence.kind}:${evidence.instanceId}:${evidence.startMs}:${evidence.endMs}:${index}`}
                  type="button"
                  className="rounded-[1.1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-left transition hover:border-primary/25 hover:bg-[hsl(var(--primary)/0.08)]"
                  onClick={() => onJumpEvidence?.(evidence)}
                  disabled={!onJumpEvidence}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 text-sm font-medium text-foreground">{evidence.title}</div>
                    <div className="shrink-0 text-xs text-[color:var(--theme-subtle-text)]">
                      {evidence.startMs === evidence.endMs
                        ? formatEvidenceTimestamp(evidence.startMs)
                        : `${formatEvidenceTimestamp(evidence.startMs)}-${formatEvidenceTimestamp(evidence.endMs)}`}
                    </div>
                  </div>
                  {evidence.preview ? <div className="mt-1 break-words text-sm leading-6 text-muted-foreground">{evidence.preview}</div> : null}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {showActions && message.content.trim() ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {onCopy ? (
              <Button type="button" size="sm" variant="outline" onClick={() => onCopy(message.content)}>
                <Copy className="h-4 w-4" />
                复制回答
              </Button>
            ) : null}
            {onRegenerate ? (
              <Button type="button" size="sm" variant="outline" onClick={onRegenerate}>
                <RotateCcw className="h-4 w-4" />
                重新生成
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function AiChatPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const pid = projectId ?? ""
  const globalSettingsPath = buildGlobalSettingsPath()

  function touchQaActivity() {
    touchDailyStudyActivity(pid, "qa", QA_ACTIVITY_WINDOW_MS)
  }

  const kindParam = searchParams.get("kind")
  const nodeIdParam = searchParams.get("nodeId")?.trim() ?? ""
  const conversationIdParam = searchParams.get("conversation")?.trim() ?? ""

  const conversations = useAiChatStore((state) => state.conversations)
  const createConversation = useAiChatStore((state) => state.createConversation)
  const appendMessages = useAiChatStore((state) => state.appendMessages)
  const replaceMessages = useAiChatStore((state) => state.replaceMessages)
  const renameConversation = useAiChatStore((state) => state.renameConversation)
  const removeConversation = useAiChatStore((state) => state.removeConversation)

  const [composerValue, setComposerValue] = useState("")
  const [pendingUserMessage, setPendingUserMessage] = useState<AiChatMessage | null>(null)
  const [streamingAssistantMessage, setStreamingAssistantMessage] = useState<AiChatMessage | null>(null)
  const [streamingMode, setStreamingMode] = useState<"append" | "replace" | null>(null)
  const [replaceBaseMessages, setReplaceBaseMessages] = useState<AiChatMessage[] | null>(null)
  const [expandedNodeIds, setExpandedNodeIds] = useState<string[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [chatError, setChatError] = useState("")
  const [historySearch, setHistorySearch] = useState("")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const streamAbortRef = useRef<AbortController | null>(null)
  const streamingContentRef = useRef("")

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const membershipQ = useMembershipSummary(authEnabled)
  const materialSourceBindingQ = useProjectMaterialSourceBinding(pid)
  const directoryBinding = useProjectDirectoryBinding(pid)
  const instancesQ = useInstances(pid)
  const taskNodesQ = useQuery({
    queryKey: ["learningTaskNodes", pid],
    queryFn: () => listLearningTaskNodes(pid),
    enabled: !!pid,
  })
  const objectNodesQ = useQuery({
    queryKey: ["learningObjectNodes", pid],
    queryFn: () => listLearningObjectNodes(pid),
    enabled: !!pid,
  })
  const recallPointQ = useQuery({
    queryKey: ["recallPoint", pid, nodeIdParam],
    queryFn: () => getRecallPoint(pid, nodeIdParam),
    enabled: !!pid && isAiChatContextKind(kindParam) && kindParam === "recall" && !!nodeIdParam && !conversationIdParam,
  })

  const projectConversations = useMemo(
    () => conversations.filter((conversation) => conversation.projectId === pid).sort((left, right) => right.updatedAt - left.updatedAt),
    [conversations, pid],
  )
  const instanceById = useMemo(
    () => new Map((instancesQ.data ?? []).map((instance) => [instance.instanceId, instance])),
    [instancesQ.data],
  )
  const selectedConversation = projectConversations.find((conversation) => conversation.id === conversationIdParam) ?? null
  const fallbackKind: AiChatContextKind =
    isAiChatContextKind(kindParam) ? kindParam : taskNodesQ.data && taskNodesQ.data.length > 0 ? "task" : "object"
  const activeKind = selectedConversation?.contextKind ?? fallbackKind

  const taskTree = useMemo(() => buildTaskSidebarTree(taskNodesQ.data ?? []), [taskNodesQ.data])
  const objectTree = useMemo(() => buildObjectSidebarTree(objectNodesQ.data ?? []), [objectNodesQ.data])
  const activeTree = activeKind === "task" ? taskTree : activeKind === "object" ? objectTree : null
  const activeNodeId = selectedConversation?.nodeId ?? (nodeIdParam || null)
  const selectedRecallPointQ = useQuery({
    queryKey: ["recallPoint", pid, activeNodeId],
    queryFn: () => getRecallPoint(pid, activeNodeId ?? ""),
    enabled: !!pid && activeKind === "recall" && !!activeNodeId,
  })
  const activeRecallPoint = activeKind === "recall" ? selectedRecallPointQ.data ?? (selectedConversation ? null : recallPointQ.data ?? null) : null
  const activeTaskRecallPointsQ = useQuery({
    queryKey: ["aiChatTaskRecallPoints", pid, activeNodeId],
    queryFn: () => listRecallPointsByLearningTaskNode(pid, activeNodeId ?? ""),
    enabled: !!pid && activeKind === "task" && !!activeNodeId,
  })
  const activeObjectRecallPointsQ = useQuery({
    queryKey: ["aiChatObjectRecallPoints", pid, activeNodeId],
    queryFn: () => listRecallPointsByLearningObjectNode(pid, activeNodeId ?? ""),
    enabled: !!pid && activeKind === "object" && !!activeNodeId,
  })
  const activeNodeLabel =
    activeKind === "task"
      ? getNodeLabel(taskTree, activeNodeId)
      : activeKind === "object"
        ? getNodeLabel(objectTree, activeNodeId)
        : describeRecallPointTitle(activeRecallPoint, activeNodeId)
  const activeNodeRecallPoints =
    activeKind === "recall"
      ? activeRecallPoint
        ? [activeRecallPoint]
        : []
      : activeKind === "task"
        ? activeTaskRecallPointsQ.data ?? []
        : activeObjectRecallPointsQ.data ?? []
  const llmConfigured = capabilitiesQ.data?.llmConfigured ?? false
  const aiChatMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const todayDateKey = getLocalDateKey()
  const interactionDisabled = !pid || !activeNodeId || !llmConfigured || aiChatMemberBlocked
  const persistedMessages = selectedConversation?.messages ?? []
  const latestAssistantIndex = useMemo(() => {
    for (let index = persistedMessages.length - 1; index >= 0; index -= 1) {
      if (persistedMessages[index]?.role === "assistant") return index
    }
    return -1
  }, [persistedMessages])
  const canRegenerate = Boolean(
    selectedConversation &&
      !isStreaming &&
      latestAssistantIndex > 0 &&
      persistedMessages[latestAssistantIndex - 1]?.role === "user",
  )

  useEffect(
    () => () => {
      streamAbortRef.current?.abort()
    },
    [],
  )

  useEffect(() => {
    if (!pid) return
    const tracker = createStudyPresenceTracker(pid)
    const touch = () => tracker.touch()
    tracker.start()
    window.addEventListener("pointerdown", touch, { passive: true })
    window.addEventListener("keydown", touch)
    window.addEventListener("wheel", touch, { passive: true })
    window.addEventListener("scroll", touch, { passive: true })
    return () => {
      window.removeEventListener("pointerdown", touch)
      window.removeEventListener("keydown", touch)
      window.removeEventListener("wheel", touch)
      window.removeEventListener("scroll", touch)
      tracker.stop()
    }
  }, [pid])

  useEffect(() => {
    if (!pid) return
    if (!capabilitiesQ.data?.authEnabled) return

    let cancelled = false

    async function runStudyMetricsSync() {
      try {
        await syncStudyMetricsSnapshot({
          projectIds: [pid],
          dateFrom: todayDateKey,
          dateTo: todayDateKey,
        })
      } catch {
        if (cancelled) return
      }
    }

    void runStudyMetricsSync()
    const timer = window.setInterval(() => {
      void runStudyMetricsSync()
    }, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [capabilitiesQ.data?.authEnabled, pid, todayDateKey])

  useEffect(() => {
    if (!activeTree) return
    const ancestorIds = collectAncestorIds(activeTree, activeNodeId)
    setExpandedNodeIds((current) =>
      Array.from(
        new Set([
          ...activeTree.rootIds,
          ...current.filter((nodeId) => nodeId in activeTree.nodeById),
          ...ancestorIds,
          ...(activeNodeId ? [activeNodeId] : []),
        ]),
      ),
    )
  }, [activeNodeId, activeTree])

  useEffect(() => {
    if (!conversationIdParam) return
    if (selectedConversation) return
    if (!pid) return
    if (activeNodeId && isAiChatContextKind(kindParam)) {
      navigate(buildAiChatPath(pid, { kind: kindParam, nodeId: activeNodeId }), { replace: true })
      return
    }
    navigate(`/p/${pid}/ai-chat`, { replace: true })
  }, [activeNodeId, conversationIdParam, kindParam, navigate, pid, selectedConversation])

  useEffect(() => {
    if (!scrollRef.current) return
    scrollRef.current.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    })
  }, [pendingUserMessage, selectedConversation?.messages.length, streamingAssistantMessage?.content])

  const visibleMessages = useMemo(() => {
    if (streamingMode === "append" && pendingUserMessage) {
      return [...persistedMessages, pendingUserMessage, streamingAssistantMessage ?? createMessage("assistant", "")]
    }
    if (streamingMode === "replace" && replaceBaseMessages && streamingAssistantMessage) {
      return [...replaceBaseMessages, streamingAssistantMessage]
    }
    return persistedMessages
  }, [pendingUserMessage, persistedMessages, replaceBaseMessages, streamingAssistantMessage, streamingMode])

  useEffect(() => {
    const latestMessage = visibleMessages.at(-1)
    if (latestMessage?.role === "assistant") {
      touchQaActivity()
    }
  }, [visibleMessages])

  function resolveActiveCourseAgentContext():
    | {
        instance: Instance
        anchorMs: number | null
        sourceKind: MaterialSourceKind
      }
    | null {
    if (!pid || !activeNodeId) return null

    let instanceId: string | null = null
    let anchorMs: number | null = null

    if (activeKind === "object") {
      const activeObjectNode = (objectNodesQ.data ?? []).find((node) => node.nodeId === activeNodeId)
      if (!activeObjectNode || activeObjectNode.kind !== "leaf") return null
      instanceId = activeObjectNode.instanceId
    } else if (activeKind === "recall") {
      if (!activeRecallPoint?.anchor) return null
      instanceId = activeRecallPoint.anchor.instanceId
      anchorMs = parseAnchorPositionMs(activeRecallPoint.anchor.position)
    } else {
      return null
    }

    if (!instanceId) return null
    const instance = instanceById.get(instanceId)
    if (!instance) return null
    const sourceKind = instance.mediaSourceKind ?? materialSourceBindingQ.data?.sourceKind
    if (!sourceKind) return null

    return {
      instance,
      anchorMs,
      sourceKind,
    }
  }

  async function loadActiveSubtitleSupplementalContext(): Promise<string | null> {
    const courseContext = resolveActiveCourseAgentContext()
    if (!courseContext) return null

    try {
      const document = await loadSubtitleDocumentForInstance({
        projectId: pid,
        instance: courseContext.instance,
        sourceKind: courseContext.sourceKind,
      })
      if (!document) return null
      return buildSubtitleContextText({
        nodeLabel: activeNodeLabel,
        fileName: document.fileName,
        segments: document.segments,
        anchorMs: courseContext.anchorMs,
      })
    } catch {
      return null
    }
  }

  async function loadActiveSupplementalContext(): Promise<string | null> {
    return await loadActiveSubtitleSupplementalContext()
  }

  async function requestChatCompletionWithContext(params: {
    baseMessages: AiChatMessage[]
    latestUserInput: string
    controller: AbortController
    systemPrompt: string
    supplementalContext?: string | null
    assistantDraft: AiChatMessage
  }): Promise<{ content: string; modelReliabilityIssue: boolean; courseEvidence?: AiChatCourseEvidence[] }> {
    const { baseMessages, latestUserInput, controller, systemPrompt, supplementalContext, assistantDraft } = params

    streamingContentRef.current = ""
    setStreamingAssistantMessage((current) => (current ? { ...current, content: "" } : { ...assistantDraft, content: "" }))

    const courseContext = resolveActiveCourseAgentContext()
    if (courseContext) {
      try {
        const result = await askCourseAgent({
          projectId: pid,
          instance: courseContext.instance,
          sourceKind: courseContext.sourceKind,
          nodeLabel: activeNodeLabel,
          userPrompt: latestUserInput,
          systemPrompt,
          anchorMs: courseContext.anchorMs,
          canCaptureVideoFrame:
            courseContext.sourceKind !== "BAIDU_NETDISK" &&
            (capabilitiesQ.data?.serverMediaStreamEnabled === true ||
              (courseContext.sourceKind === "BROWSER_LOCAL" && directoryBinding.permission === "granted")),
          historyMessages: baseMessages
            .filter((message): message is AiChatMessage & { role: "user" | "assistant" } => message.role === "user" || message.role === "assistant")
            .map((message) => ({
              role: message.role,
              content: message.content,
            })),
          temperature: 0.2,
          signal: controller.signal,
          timeoutMs: 90_000,
          onStatus: (status) => {
            touchQaActivity()
            setStreamingAssistantMessage((current) => (current ? { ...current, content: status } : { ...assistantDraft, content: status }))
          },
        })

        touchQaActivity()
        streamingContentRef.current = result.content
        setStreamingAssistantMessage((current) => (current ? { ...current, content: result.content } : { ...assistantDraft, content: result.content }))

        const hasNodeContentContext = activeNodeRecallPoints.some((item) => item.state === "ACTIVE")
        const missingContext = hasNodeContentContext ? responseLooksLikeMissingContext(result.content) : false
        const offTopic = hasNodeContentContext
          ? responseLooksOffTopic(result.content, {
              nodeLabel: activeNodeLabel,
              recallPoints: activeNodeRecallPoints,
            })
          : false

        return {
          content: result.content,
          modelReliabilityIssue: missingContext || offTopic,
          courseEvidence: result.evidence,
        }
      } catch (error) {
        if (controller.signal.aborted) throw error
      }
    }

    const resolvedSupplementalContext = supplementalContext === undefined ? await loadActiveSupplementalContext() : supplementalContext
    const result = await askProjectLlmStream(
      pid,
      {
        prompt: buildConversationPrompt(baseMessages, latestUserInput),
        systemPrompt,
        supplementalContext: resolvedSupplementalContext ?? undefined,
        recallPointId: activeKind === "recall" ? (activeNodeId ?? undefined) : undefined,
        learningTaskNodeId: activeKind === "task" ? (activeNodeId ?? undefined) : undefined,
        learningObjectNodeId: activeKind === "object" ? (activeNodeId ?? undefined) : undefined,
        temperature: 0.2,
      },
      {
        timeoutMs: 90_000,
        signal: controller.signal,
        onDelta: (_chunk, accumulated) => {
          touchQaActivity()
          streamingContentRef.current = accumulated
          setStreamingAssistantMessage((current) => (current ? { ...current, content: accumulated } : { ...assistantDraft, content: accumulated }))
        },
      },
    )

    touchQaActivity()
    const hasNodeContentContext = activeNodeRecallPoints.some((item) => item.state === "ACTIVE")
    const missingContext = hasNodeContentContext ? responseLooksLikeMissingContext(result.content) : false
    const offTopic = hasNodeContentContext
      ? responseLooksOffTopic(result.content, {
          nodeLabel: activeNodeLabel,
          recallPoints: activeNodeRecallPoints,
        })
      : false

    return {
      content: result.content,
      modelReliabilityIssue: missingContext || offTopic,
      courseEvidence: [],
    }
  }

  function navigateToContext(params: { kind: AiChatContextKind; nodeId: string; conversationId?: string | null }) {
    if (!pid) return
    navigate(buildAiChatPath(pid, params))
  }

  function handleJumpToEvidence(evidence: AiChatCourseEvidence) {
    if (!pid) return
    touchQaActivity()
    const search = new URLSearchParams()
    search.set("instanceId", evidence.instanceId)
    search.set("position", `t=${Math.max(0, Math.floor((evidence.startMs + evidence.endMs) / 2))}`)
    navigate(`/p/${pid}/workbench?${search.toString()}`)
  }

  function resetStreamingState() {
    setPendingUserMessage(null)
    setStreamingAssistantMessage(null)
    setStreamingMode(null)
    setReplaceBaseMessages(null)
    setIsStreaming(false)
    streamingContentRef.current = ""
  }

  function handleSelectNode(nodeId: string) {
    if (!pid || isStreaming) return
    const switchingContext = activeNodeId !== nodeId
    setMobileSidebarOpen(false)
    setChatError("")
    navigateToContext({ kind: activeKind, nodeId })
    if (switchingContext) {
      showSuccessFeedback("已切换问答上下文", "新节点会从新会话开始，旧会话已经保留在历史列表里。")
    }
  }

  function handleSelectConversation(conversation: AiChatConversation) {
    if (!pid) return
    setMobileSidebarOpen(false)
    setChatError("")
    navigateToContext({
      kind: conversation.contextKind,
      nodeId: conversation.nodeId,
      conversationId: conversation.id,
    })
  }

  function handleStartNewConversation() {
    if (!pid || !activeNodeId) return
    setMobileSidebarOpen(false)
    setChatError("")
    navigateToContext({ kind: activeKind, nodeId: activeNodeId })
  }

  function persistConversationTurn(userMessage: AiChatMessage, followUpMessages: AiChatMessage[]) {
    if (selectedConversation) {
      appendMessages(selectedConversation.id, [userMessage, ...followUpMessages])
      return
    }
    const createdConversationId = createConversation({
      projectId: pid,
      contextKind: activeKind,
      nodeId: activeNodeId ?? "",
      messages: [userMessage, ...followUpMessages],
    })
    navigateToContext({
      kind: activeKind,
      nodeId: activeNodeId ?? "",
      conversationId: createdConversationId,
    })
  }

  function shouldTriggerModelReliabilityGate(messagesBeforeCurrentTurn: AiChatMessage[], currentTurnHasReliabilityIssue: boolean) {
    if (!currentTurnHasReliabilityIssue) return false
    const previousIssueCount = countTrailingModelReliabilityIssues(messagesBeforeCurrentTurn)
    return previousIssueCount < 2 && previousIssueCount + 1 >= 2
  }

  function toggleNodeExpanded(nodeId: string) {
    setExpandedNodeIds((current) => (current.includes(nodeId) ? current.filter((item) => item !== nodeId) : [...current, nodeId]))
  }

  function resolveNodeLabel(kind: AiChatContextKind, nodeId: string) {
    if (kind === "task") return getNodeLabel(taskTree, nodeId)
    if (kind === "object") return getNodeLabel(objectTree, nodeId)
    if (activeKind === "recall" && activeNodeId === nodeId) return describeRecallPointTitle(activeRecallPoint, nodeId)
    return formatRecallPointReference(nodeId, "复述点待确认")
  }

  function handleRenameConversation(conversation: AiChatConversation) {
    if (typeof window === "undefined") return
    const nextTitle = window.prompt("重命名会话", conversation.title)
    if (nextTitle === null) return
    const trimmedTitle = nextTitle.trim()
    if (!trimmedTitle || trimmedTitle === conversation.title) return
    renameConversation(conversation.id, trimmedTitle)
  }

  function handleDeleteConversation(conversation: AiChatConversation) {
    if (typeof window !== "undefined" && !window.confirm(`确认删除会话“${conversation.title}”吗？`)) {
      return
    }
    removeConversation(conversation.id)
    if (selectedConversation?.id === conversation.id) {
      navigateToContext({
        kind: conversation.contextKind,
        nodeId: conversation.nodeId,
      })
    }
  }

  async function handleCopyResponse(content: string) {
    try {
      touchQaActivity()
      await copyText(content)
      showSuccessFeedback("回答已复制", "这条回答已经复制到剪贴板。")
    } catch (err) {
      showErrorFeedback("复制回答失败", formatApiError(err))
    }
  }

  async function handleClearConversation() {
    if (!selectedConversation) return
    if (typeof window !== "undefined" && !window.confirm("确认清空当前会话吗？清空后会回到同一节点下的新会话。")) {
      return
    }
    removeConversation(selectedConversation.id)
    setChatError("")
    navigateToContext({ kind: selectedConversation.contextKind, nodeId: selectedConversation.nodeId })
  }

  function handleStopStreaming() {
    touchQaActivity()
    streamAbortRef.current?.abort()
  }

  function handleApplyQuickAction(prompt: string) {
    touchQaActivity()
    setComposerValue(prompt)
    if (typeof window !== "undefined") {
      window.requestAnimationFrame(() => {
        composerRef.current?.focus()
        const textLength = prompt.length
        composerRef.current?.setSelectionRange(textLength, textLength)
      })
    }
  }

  async function handleSend() {
    const trimmed = composerValue.trim()
    if (!trimmed || !pid || !activeNodeId || !llmConfigured || aiChatMemberBlocked || isStreaming) return

    touchQaActivity()
    const userMessage = createMessage("user", trimmed)
    const assistantDraft = createMessage("assistant", "")
    const controller = new AbortController()
    streamAbortRef.current = controller
    setChatError("")
    setPendingUserMessage(userMessage)
    setStreamingAssistantMessage(assistantDraft)
    setStreamingMode("append")
    setReplaceBaseMessages(null)
    setComposerValue("")
    setIsStreaming(true)
    streamingContentRef.current = ""

    try {
      const result = await requestChatCompletionWithContext({
        baseMessages: persistedMessages,
        latestUserInput: trimmed,
        controller,
        systemPrompt: buildChatSystemPrompt(activeKind, activeNodeLabel),
        assistantDraft,
      })
      const finalAssistantMessage = createMessage("assistant", result.content, {
        modelReliabilityIssue: result.modelReliabilityIssue,
        courseEvidence: result.courseEvidence,
      })
      const followUpMessages: AiChatMessage[] = [finalAssistantMessage]
      if (shouldTriggerModelReliabilityGate(persistedMessages, result.modelReliabilityIssue)) {
        followUpMessages.push(createMessage("system", buildModelReliabilityGateMessage()))
      }
      persistConversationTurn(userMessage, followUpMessages)
    } catch (err) {
      const partialContent = streamingContentRef.current
      if (controller.signal.aborted) {
        if (partialContent.trim()) {
          persistConversationTurn(userMessage, [
            {
              ...assistantDraft,
              content: partialContent,
            },
          ])
        } else {
          setComposerValue(trimmed)
        }
        return
      }
      setComposerValue(trimmed)
      const message = formatApiError(err)
      setChatError(message)
      showErrorFeedback("AI 问答失败", message)
    } finally {
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null
      }
      resetStreamingState()
    }
  }

  async function handleRegenerateLastAnswer() {
    if (!selectedConversation || !pid || !activeNodeId || !llmConfigured || aiChatMemberBlocked || isStreaming || !canRegenerate || latestAssistantIndex < 1) return

    const latestUserMessage = persistedMessages[latestAssistantIndex - 1]
    if (!latestUserMessage || latestUserMessage.role !== "user") return

    touchQaActivity()
    const messagesBeforeLatestTurn = persistedMessages.slice(0, latestAssistantIndex - 1)
    const baseMessagesForReplace = [...messagesBeforeLatestTurn, latestUserMessage]
    const assistantDraft = createMessage("assistant", "")
    const controller = new AbortController()
    streamAbortRef.current = controller
    setChatError("")
    setPendingUserMessage(null)
    setStreamingAssistantMessage(assistantDraft)
    setStreamingMode("replace")
    setReplaceBaseMessages(baseMessagesForReplace)
    setIsStreaming(true)
    streamingContentRef.current = ""

    try {
      const result = await requestChatCompletionWithContext({
        baseMessages: messagesBeforeLatestTurn,
        latestUserInput: latestUserMessage.content,
        controller,
        systemPrompt: buildChatSystemPrompt(activeKind, activeNodeLabel),
        assistantDraft,
      })
      const replacementMessages: AiChatMessage[] = [
        ...baseMessagesForReplace,
        createMessage("assistant", result.content, {
          modelReliabilityIssue: result.modelReliabilityIssue,
          courseEvidence: result.courseEvidence,
        }),
      ]
      if (shouldTriggerModelReliabilityGate(messagesBeforeLatestTurn, result.modelReliabilityIssue)) {
        replacementMessages.push(createMessage("system", buildModelReliabilityGateMessage()))
      }
      replaceMessages(selectedConversation.id, replacementMessages)
    } catch (err) {
      const partialContent = streamingContentRef.current
      if (controller.signal.aborted) {
        if (partialContent.trim()) {
          replaceMessages(selectedConversation.id, [...baseMessagesForReplace, { ...assistantDraft, content: partialContent }])
        }
      } else {
        const message = formatApiError(err)
        setChatError(message)
        showErrorFeedback("重新生成失败", message)
      }
    } finally {
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null
      }
      resetStreamingState()
    }
  }

  if (!pid) {
    return (
      <ContentNotice
        title="当前页面缺少项目上下文"
        message="AI 问答需要绑定到具体项目。请先回到项目内的学习任务节点或学习对象节点，再从详情页进入。"
        action={
          <Button asChild>
            <Link to="/projects">返回项目中心</Link>
          </Button>
        }
      />
    )
  }

  return (
    <>
      <Dialog open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <DialogContent className="max-w-[24rem] rounded-[1.75rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-0 xl:hidden">
          <DialogHeader className="border-b border-[color:var(--theme-soft-border)] px-5 py-4">
            <DialogTitle className="text-xl tracking-tight text-foreground">目录与会话</DialogTitle>
          </DialogHeader>
          <div className="max-h-[80vh] overflow-y-auto px-4 py-4">
            <SidebarPanel
              activeKind={activeKind}
              activeTree={activeTree}
              activeNodeId={activeNodeId}
              expandedNodeIds={expandedNodeIds}
              isStreaming={isStreaming}
              conversations={projectConversations}
              selectedConversationId={selectedConversation?.id ?? null}
              searchValue={historySearch}
              resolveNodeLabel={resolveNodeLabel}
              onToggleNode={toggleNodeExpanded}
              onSelectNode={handleSelectNode}
              onSearchChange={setHistorySearch}
              onNewConversation={handleStartNewConversation}
              onSelectConversation={handleSelectConversation}
              onRenameConversation={handleRenameConversation}
              onDeleteConversation={handleDeleteConversation}
            />
          </div>
        </DialogContent>
      </Dialog>

      <div
        className={cn(
          "grid min-h-[calc(100dvh-8.75rem)] gap-5",
          sidebarCollapsed ? "xl:grid-cols-[4.75rem_minmax(0,1fr)]" : "xl:grid-cols-[20rem_minmax(0,1fr)]",
        )}
      >
        <aside className="hidden xl:block">
          {sidebarCollapsed ? (
            <div className="sticky top-28 flex flex-col gap-3 rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-3 shadow-[var(--theme-soft-shadow)]">
              <Button type="button" variant="outline" size="icon" onClick={() => setSidebarCollapsed(false)} aria-label="展开左侧栏">
                <PanelLeftOpen className="h-4 w-4" />
              </Button>
              <Button type="button" variant="outline" size="icon" onClick={handleStartNewConversation} disabled={!activeNodeId || isStreaming} aria-label="新会话">
                <MessageSquarePlus className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="sticky top-28 max-h-[calc(100dvh-8.75rem)] overflow-y-auto">
              <SidebarPanel
                activeKind={activeKind}
                activeTree={activeTree}
                activeNodeId={activeNodeId}
                expandedNodeIds={expandedNodeIds}
                isStreaming={isStreaming}
                conversations={projectConversations}
                selectedConversationId={selectedConversation?.id ?? null}
                searchValue={historySearch}
                resolveNodeLabel={resolveNodeLabel}
                onToggleNode={toggleNodeExpanded}
                onSelectNode={handleSelectNode}
                onSearchChange={setHistorySearch}
                onNewConversation={handleStartNewConversation}
                onSelectConversation={handleSelectConversation}
                onRenameConversation={handleRenameConversation}
                onDeleteConversation={handleDeleteConversation}
                canCollapseSidebar
                onCollapseSidebar={() => setSidebarCollapsed(true)}
              />
            </div>
          )}
        </aside>

        <section className="flex min-h-[calc(100dvh-8.75rem)] flex-col overflow-hidden rounded-[2rem] border border-[color:var(--theme-soft-border)] bg-[linear-gradient(180deg,hsl(var(--background)/0.96),hsl(var(--background)/0.92))] shadow-[0_34px_90px_-46px_rgba(15,23,42,0.28)]">
          <div className="border-b border-[color:var(--theme-soft-border)] px-5 py-4 sm:px-7">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="theme-meta-strong">{describeAiChatContextKind(activeKind)}</span>
                  <span className="truncate text-lg font-semibold tracking-tight text-foreground">{activeNodeLabel}</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" className="xl:hidden" onClick={() => setMobileSidebarOpen(true)}>
                  <Menu className="h-4 w-4" />
                  目录与会话
                </Button>
                {selectedConversation ? (
                  <Button type="button" variant="outline" onClick={() => void handleClearConversation()} disabled={isStreaming}>
                    <Trash2 className="h-4 w-4" />
                    清空会话
                  </Button>
                ) : null}
                <Button type="button" variant="outline" onClick={handleStartNewConversation} disabled={isStreaming || !activeNodeId}>
                  <MessageSquarePlus className="h-4 w-4" />
                  新会话
                </Button>
              </div>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-7" onScroll={touchQaActivity}>
            {capabilitiesQ.isLoading && !capabilitiesQ.data ? (
              <LoadingNotice title="正在准备 AI 问答" message="正在确认当前账号是否已经接通可用的大模型能力。" />
            ) : null}
            {capabilitiesQ.error && !capabilitiesQ.data ? <ErrorNotice title="AI 能力状态加载失败" message={formatApiError(capabilitiesQ.error)} /> : null}
            {taskNodesQ.error && activeKind === "task" ? <ErrorNotice title="任务节点目录加载失败" message={formatApiError(taskNodesQ.error)} /> : null}
            {objectNodesQ.error && activeKind === "object" ? <ErrorNotice title="对象节点目录加载失败" message={formatApiError(objectNodesQ.error)} /> : null}

            {aiChatMemberBlocked && !capabilitiesQ.isLoading ? (
              <MemberOnlyFeatureNotice
                className="mx-auto max-w-3xl"
                title="AI 问答是会员专属功能"
                message="当前账号还没有有效会员，所以这里先不开放 AI 问答。开通会员后，就可以继续使用项目问答和节点上下文提问。"
              />
            ) : null}

            {!aiChatMemberBlocked && !llmConfigured && !capabilitiesQ.isLoading ? (
              <ContentNotice
                title="当前还没有接通可用的 LLM"
                message={
                  capabilitiesQ.data?.authEnabled
                    ? "请先到全局设置里的“大模型配置”保存 Base URL、模型名和 API Key，然后再回来提问。"
                    : "请先到全局设置里的“大模型配置”填写 Base URL、模型名和 API Key，然后再回来提问。"
                }
                action={
                  <Button asChild>
                    <Link to={globalSettingsPath}>前往全局设置</Link>
                  </Button>
                }
              />
            ) : null}

            {llmConfigured && !aiChatMemberBlocked && !activeNodeId ? (
              <div className="mx-auto max-w-3xl px-2 pt-2 text-sm leading-7 text-muted-foreground">请从左侧选择一个节点</div>
            ) : null}

            {chatError ? <ErrorNotice title="本轮问答失败" message={chatError} className="mx-auto mb-5 max-w-3xl" /> : null}

            {llmConfigured && !aiChatMemberBlocked && activeNodeId && visibleMessages.length === 0 ? (
              <div className="mx-auto flex max-w-3xl flex-col items-center px-2 pt-16 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-[1.75rem] bg-[linear-gradient(135deg,hsl(var(--primary)),hsl(var(--primary)/0.72))] text-primary-foreground shadow-[0_24px_48px_-26px_hsl(var(--primary)/0.5)]">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h1 className="mt-6 text-3xl font-semibold tracking-tight text-foreground">从当前节点开始提问</h1>
                <p className="mt-3 max-w-2xl text-[15px] leading-7 text-muted-foreground">
                  当前上下文是{describeAiChatContextKind(activeKind)}“{activeNodeLabel}”。你可以直接问概念理解、结构梳理、复习建议，或者让 AI 基于当前节点帮你展开解释。
                </p>
              </div>
            ) : null}

            {llmConfigured && !aiChatMemberBlocked && activeNodeId && visibleMessages.length > 0 ? (
              <div className="mx-auto max-w-3xl space-y-8">
                {visibleMessages.map((message, index) => {
                  let latestAssistantVisibleIndex = -1
                  for (let cursor = visibleMessages.length - 1; cursor >= 0; cursor -= 1) {
                    if (visibleMessages[cursor]?.role === "assistant") {
                      latestAssistantVisibleIndex = cursor
                      break
                    }
                  }
                  const isLatestAssistant = message.role === "assistant" && index === latestAssistantVisibleIndex
                  return (
                    <ChatMessageRow
                      key={message.id}
                      message={message}
                      pendingAssistant={isStreaming && isLatestAssistant}
                      showActions={isLatestAssistant && !isStreaming}
                      onJumpEvidence={message.courseEvidence && message.courseEvidence.length > 0 ? handleJumpToEvidence : undefined}
                      onCopy={isLatestAssistant ? (content) => void handleCopyResponse(content) : undefined}
                      onRegenerate={isLatestAssistant && canRegenerate ? () => void handleRegenerateLastAnswer() : undefined}
                    />
                  )
                })}
              </div>
            ) : null}
          </div>

          <div className="border-t border-[color:var(--theme-soft-border)] px-4 py-4 sm:px-7">
            <div className="mx-auto max-w-3xl">
              <div className="rounded-[1.9rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] shadow-[0_28px_64px_-40px_rgba(15,23,42,0.24)]">
                <textarea
                  ref={composerRef}
                  value={composerValue}
                  onChange={(event) => {
                    touchQaActivity()
                    setComposerValue(event.target.value)
                  }}
                  onFocus={touchQaActivity}
                  onClick={touchQaActivity}
                  onKeyDown={(event) => {
                    touchQaActivity()
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault()
                      void handleSend()
                    }
                  }}
                  rows={4}
                  className="min-h-[7.5rem] w-full resize-none rounded-[1.9rem] bg-transparent px-5 py-4 text-[15px] leading-7 text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder={activeNodeId ? `围绕“${activeNodeLabel}”继续提问...` : "先从左侧选择一个上下文，再开始提问"}
                  disabled={isStreaming || interactionDisabled}
                />
                <div className="flex flex-col gap-3 border-t border-[color:var(--theme-soft-border)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    {QUICK_CHAT_ACTIONS.map((action) => (
                      <button
                        key={action.label}
                        type="button"
                        className="inline-flex h-8 items-center rounded-full border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-3 text-xs font-medium text-[color:var(--theme-subtle-text)] transition hover:border-primary/18 hover:bg-[hsl(var(--primary)/0.08)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-55"
                        onClick={() => handleApplyQuickAction(action.prompt)}
                        disabled={isStreaming || interactionDisabled}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                  {isStreaming ? (
                    <Button type="button" variant="outline" onClick={handleStopStreaming}>
                      <Square className="h-4 w-4 fill-current" />
                      停止生成
                    </Button>
                  ) : (
                    <Button type="button" onClick={() => void handleSend()} disabled={interactionDisabled || !composerValue.trim()}>
                      发送
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}
