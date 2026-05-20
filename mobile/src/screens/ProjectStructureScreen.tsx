import { useMemo, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { LearningTaskNode } from "../api/learningTaskNodes"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

type StructureMode = "task" | "object"

type TreeRow = {
  childCount: number
  depth: number
  id: string
  kind: "container" | "leaf"
  meta: string
  title: string
}

export function ProjectStructureScreen({
  learningObjectNodes,
  learningObjectNodesErrorMessage,
  learningObjectNodesLoading,
  learningTaskNodes,
  learningTaskNodesErrorMessage,
  learningTaskNodesLoading,
}: {
  learningObjectNodes: LearningObjectNode[]
  learningObjectNodesErrorMessage?: string | null
  learningObjectNodesLoading: boolean
  learningTaskNodes: LearningTaskNode[]
  learningTaskNodesErrorMessage?: string | null
  learningTaskNodesLoading: boolean
}) {
  const [mode, setMode] = useState<StructureMode>("task")
  const taskRows = useMemo(() => buildTaskRows(learningTaskNodes), [learningTaskNodes])
  const objectRows = useMemo(() => buildObjectRows(learningObjectNodes), [learningObjectNodes])
  const rows = mode === "task" ? taskRows : objectRows
  const loading = mode === "task" ? learningTaskNodesLoading : learningObjectNodesLoading
  const errorMessage = mode === "task" ? learningTaskNodesErrorMessage : learningObjectNodesErrorMessage

  return (
    <Screen>
      <Text style={styles.title}>结构视图</Text>
      <View style={styles.modeRow}>
        <ModeButton active={mode === "task"} label="学习任务树" onPress={() => setMode("task")} />
        <ModeButton active={mode === "object"} label="学习对象树" onPress={() => setMode("object")} />
      </View>

      {loading ? <LoadingState label={mode === "task" ? "加载学习任务树" : "加载学习对象树"} /> : null}
      {errorMessage ? <EmptyState title={errorMessage} /> : null}
      {!loading && !errorMessage && rows.length === 0 ? (
        <EmptyState title={mode === "task" ? "当前项目还没有学习任务树" : "当前项目还没有学习对象树"} />
      ) : null}
      {!loading && !errorMessage && rows.length > 0 ? (
        <View style={styles.tree}>
          {rows.map((row) => (
            <View key={row.id} style={[styles.row, { paddingLeft: row.depth * 18 }]}>
              <View style={[styles.nodeMark, row.kind === "leaf" && styles.nodeMarkLeaf]} />
              <View style={styles.rowText}>
                <Text style={styles.rowTitle}>{row.title}</Text>
                <Text style={styles.rowMeta}>{row.meta}</Text>
              </View>
            </View>
          ))}
        </View>
      ) : null}
    </Screen>
  )
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

function buildTaskRows(nodes: LearningTaskNode[]) {
  const byId = Object.fromEntries(nodes.map((node) => [node.nodeId, node])) as Record<string, LearningTaskNode>
  const childIdsByParentId = buildChildIdsByParentId(nodes)
  const rootIds = nodes
    .filter((node) => !node.parentId)
    .map((node) => node.nodeId)
    .sort((a, b) => a.localeCompare(b))
  const rows: TreeRow[] = []
  for (const rootId of rootIds) {
    appendTaskRow(rootId, byId, childIdsByParentId, rows, 0, new Set())
  }
  return rows
}

function appendTaskRow(
  nodeId: string,
  byId: Record<string, LearningTaskNode>,
  childIdsByParentId: Record<string, string[]>,
  rows: TreeRow[],
  depth: number,
  visiting: Set<string>,
) {
  if (visiting.has(nodeId)) return
  const node = byId[nodeId]
  if (!node) return
  const childIds = childIdsByParentId[nodeId] ?? []
  rows.push({
    childCount: childIds.length,
    depth,
    id: node.nodeId,
    kind: node.kind,
    meta: node.kind === "leaf" ? "学习任务" : `${childIds.length} 个分支`,
    title: node.title.trim() || (node.kind === "leaf" ? "未命名任务" : "未命名分组"),
  })
  visiting.add(nodeId)
  for (const childId of childIds) appendTaskRow(childId, byId, childIdsByParentId, rows, depth + 1, visiting)
  visiting.delete(nodeId)
}

function buildObjectRows(nodes: LearningObjectNode[]) {
  const byId = Object.fromEntries(nodes.map((node) => [node.nodeId, node])) as Record<string, LearningObjectNode>
  const childIdsByParentId = buildChildIdsByParentId(nodes)
  const rootIds = nodes
    .filter((node) => !node.parentId)
    .map((node) => node.nodeId)
    .sort((a, b) => a.localeCompare(b))
  const rows: TreeRow[] = []
  for (const rootId of rootIds) {
    appendObjectRow(rootId, byId, childIdsByParentId, rows, 0, new Set())
  }
  return rows
}

function appendObjectRow(
  nodeId: string,
  byId: Record<string, LearningObjectNode>,
  childIdsByParentId: Record<string, string[]>,
  rows: TreeRow[],
  depth: number,
  visiting: Set<string>,
) {
  if (visiting.has(nodeId)) return
  const node = byId[nodeId]
  if (!node) return
  const childIds = childIdsByParentId[nodeId] ?? []
  rows.push({
    childCount: childIds.length,
    depth,
    id: node.nodeId,
    kind: node.kind,
    meta: node.kind === "leaf" ? "学习对象" : `${childIds.length} 个子节点`,
    title: formatObjectTitle(node, depth),
  })
  visiting.add(nodeId)
  for (const childId of childIds) appendObjectRow(childId, byId, childIdsByParentId, rows, depth + 1, visiting)
  visiting.delete(nodeId)
}

function buildChildIdsByParentId<T extends { nodeId: string; parentId: string | null; kind: string; children?: string[] }>(
  nodes: T[],
) {
  const nodeIds = new Set(nodes.map((node) => node.nodeId))
  const childIdsByParentId: Record<string, string[]> = {}
  for (const node of nodes) {
    if (node.kind === "container") {
      for (const childId of node.children ?? []) {
        if (!nodeIds.has(childId)) continue
        childIdsByParentId[node.nodeId] ??= []
        if (!childIdsByParentId[node.nodeId].includes(childId)) childIdsByParentId[node.nodeId].push(childId)
      }
    }
    if (node.parentId && nodeIds.has(node.parentId)) {
      childIdsByParentId[node.parentId] ??= []
      if (!childIdsByParentId[node.parentId].includes(node.nodeId)) childIdsByParentId[node.parentId].push(node.nodeId)
    }
  }
  for (const childIds of Object.values(childIdsByParentId)) childIds.sort((a, b) => a.localeCompare(b))
  return childIdsByParentId
}

function formatObjectTitle(node: LearningObjectNode, depth: number) {
  const rawTitle = node.title.trim()
  if (!rawTitle && node.kind === "leaf") return "未命名内容"
  if (!rawTitle && node.kind === "container") return depth === 0 ? "学习对象根" : "未命名分组"
  if (depth === 0 && rawTitle === "Files") return "学习对象根"
  return rawTitle
}

const styles = StyleSheet.create({
  modeButton: {
    alignItems: "center",
    borderColor: ui.colors.border,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    flex: 1,
    minHeight: 40,
    justifyContent: "center",
  },
  modeButtonActive: { backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  modeRow: { flexDirection: "row", gap: ui.spacing.sm },
  modeText: { color: ui.colors.textMuted, fontSize: ui.type.control, fontWeight: "700" },
  modeTextActive: { color: ui.colors.primaryText },
  nodeMark: {
    backgroundColor: ui.colors.textSoft,
    borderRadius: 4,
    height: 8,
    marginTop: 7,
    width: 8,
  },
  nodeMarkLeaf: { backgroundColor: ui.colors.primary },
  row: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: ui.spacing.sm,
    paddingVertical: ui.spacing.md,
  },
  rowMeta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  rowText: { flex: 1, gap: ui.spacing.xs },
  rowTitle: { color: ui.colors.text, fontSize: ui.type.control, fontWeight: "700", lineHeight: 21 },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
  tree: { gap: 0 },
})
