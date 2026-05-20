import { useState, type ReactNode } from "react"
import { Modal, Pressable, StyleSheet, Text, View } from "react-native"
import { router } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { MineScreen } from "../screens/MineScreen"
import { ui } from "../constants/ui"
import { ContextMenu } from "./ContextMenu"
import { PROJECT_SHELL_DESTINATIONS, type LearningContextInput, type ProjectShellDestinationId } from "./mobileNavigation"

export type ProjectShellAction = {
  label: string
  onPress: () => void
}

export function ProjectShell({
  context,
  openGlobalSettings,
  pageActions,
  renderAi,
  renderLearning,
  renderReview,
  renderStructure,
  signOut,
}: {
  context: LearningContextInput
  openGlobalSettings: () => void
  pageActions?: ProjectShellAction[]
  renderAi: () => ReactNode
  renderLearning: () => ReactNode
  renderReview: () => ReactNode
  renderStructure: () => ReactNode
  signOut: () => void
}) {
  const [activeDestination, setActiveDestination] = useState<ProjectShellDestinationId>("learning")
  const [contextMenuVisible, setContextMenuVisible] = useState(false)
  const [pageMenuVisible, setPageMenuVisible] = useState(false)
  const contextTitle = [context.subjectTitle, context.projectTitle].filter(Boolean).join(" · ") || "当前项目"
  const projectActions = buildProjectActions(context)
  const activePageActions = activeDestination === "learning" ? pageActions ?? [] : []

  return (
    <SafeAreaView edges={["top"]} style={styles.root}>
      <View style={styles.topBar}>
        <View style={styles.topSide} />
        <Pressable
          accessibilityRole="button"
          onPress={() => setContextMenuVisible(true)}
          style={styles.contextButton}
        >
          <Text maxFontSizeMultiplier={1.1} numberOfLines={1} style={styles.contextTitle}>
            {contextTitle}
          </Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => setPageMenuVisible(true)}
          style={styles.moreButton}
        >
          <Text maxFontSizeMultiplier={1.1} style={styles.moreText}>⌬</Text>
        </Pressable>
      </View>
      <ContextMenu context={context} onDismiss={() => setContextMenuVisible(false)} visible={contextMenuVisible} />
      <PageMenu
        onDismiss={() => setPageMenuVisible(false)}
        pageActions={activePageActions}
        projectActions={projectActions}
        visible={pageMenuVisible}
      />

      <View style={styles.content}>
        {activeDestination === "learning" ? renderLearning() : null}
        {activeDestination === "ai" ? renderAi() : null}
        {activeDestination === "review" ? renderReview() : null}
        {activeDestination === "structure" ? renderStructure() : null}
        {activeDestination === "mine" ? (
          <MineScreen openGlobalSettings={openGlobalSettings} signOut={signOut} />
        ) : null}
      </View>

      <View style={styles.bottomBar}>
        {PROJECT_SHELL_DESTINATIONS.map((destination) => {
          const active = activeDestination === destination.id
          return (
            <Pressable
              accessibilityRole="button"
              key={destination.id}
              onPress={() => setActiveDestination(destination.id)}
              style={styles.tab}
            >
              <Text maxFontSizeMultiplier={1.1} style={[styles.tabIcon, active && styles.tabIconActive]}>
                {PROJECT_TAB_ICONS[destination.id]}
              </Text>
              <Text maxFontSizeMultiplier={1.1} style={[styles.tabLabel, active && styles.tabLabelActive]}>
                {destination.label}
              </Text>
            </Pressable>
          )
        })}
      </View>
    </SafeAreaView>
  )
}

const PROJECT_TOP_BAR_HEIGHT = 58

const PROJECT_TAB_ICONS: Record<ProjectShellDestinationId, string> = {
  ai: "✦",
  learning: "▰",
  mine: "●",
  review: "▣",
  structure: "⌯",
}

function buildProjectActions(context: LearningContextInput): ProjectShellAction[] {
  if (!context.subjectId || !context.scopedProjectId) return []

  return [
    {
      label: "项目设置",
      onPress: () =>
        router.push({
          pathname: "/project-settings/[subjectId]/[scopedProjectId]",
          params: { scopedProjectId: context.scopedProjectId ?? "", subjectId: context.subjectId ?? "" },
        }),
    },
    {
      label: "项目中心",
      onPress: () => router.push({ pathname: "/subject/[subjectId]", params: { subjectId: context.subjectId ?? "" } }),
    },
  ]
}

function PageMenu({
  onDismiss,
  pageActions,
  projectActions,
  visible,
}: {
  onDismiss: () => void
  pageActions: ProjectShellAction[]
  projectActions: ProjectShellAction[]
  visible: boolean
}) {
  return (
    <Modal animationType="fade" onRequestClose={onDismiss} transparent visible={visible}>
      <Pressable accessibilityRole="button" onPress={onDismiss} style={styles.menuScrim} />
      <SafeAreaView edges={["top"]} pointerEvents="box-none" style={styles.menuLayer}>
        <View style={styles.pageMenu}>
          {pageActions.length > 0 ? <Text maxFontSizeMultiplier={1.1} style={styles.menuTitle}>页面操作</Text> : null}
          {pageActions.map((item) => (
            <Pressable
              accessibilityRole="button"
              key={item.label}
              onPress={() => {
                onDismiss()
                item.onPress()
              }}
              style={styles.menuItem}
            >
              <Text maxFontSizeMultiplier={1.1} style={styles.menuItemText}>{item.label}</Text>
            </Pressable>
          ))}
          {projectActions.length > 0 ? <Text maxFontSizeMultiplier={1.1} style={styles.menuTitle}>当前项目</Text> : null}
          {projectActions.map((item) => (
            <Pressable
              accessibilityRole="button"
              key={item.label}
              onPress={() => {
                onDismiss()
                item.onPress()
              }}
              style={styles.menuItem}
            >
              <Text maxFontSizeMultiplier={1.1} style={styles.menuItemText}>{item.label}</Text>
            </Pressable>
          ))}
        </View>
      </SafeAreaView>
    </Modal>
  )
}

const styles = StyleSheet.create({
  bottomBar: {
    backgroundColor: ui.colors.surface,
    borderTopColor: ui.colors.borderSoft,
    borderTopWidth: 1,
    flexDirection: "row",
    minHeight: 72,
    paddingBottom: ui.spacing.sm,
    paddingTop: ui.spacing.xs,
  },
  content: { flex: 1 },
  contextButton: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: ui.spacing.xs,
    justifyContent: "center",
    minWidth: 0,
  },
  contextTitle: { color: ui.colors.text, flexShrink: 1, fontSize: 20, fontWeight: "800" },
  menuItem: { paddingVertical: ui.spacing.md },
  menuItemText: { color: ui.colors.text, fontSize: ui.type.control, fontWeight: "700" },
  menuLayer: {
    bottom: 0,
    left: 0,
    pointerEvents: "box-none",
    position: "absolute",
    right: 0,
    top: 0,
  },
  menuScrim: {
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  menuTitle: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "700", paddingTop: ui.spacing.xs },
  moreButton: { alignItems: "center", height: 38, justifyContent: "center", width: 38 },
  moreText: { color: ui.colors.text, fontSize: 28, fontWeight: "800", lineHeight: 30 },
  pageMenu: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    gap: ui.spacing.xs,
    paddingHorizontal: ui.spacing.lg,
    paddingVertical: ui.spacing.md,
    alignSelf: "flex-end",
    marginRight: ui.spacing.screenX,
    marginTop: PROJECT_TOP_BAR_HEIGHT + ui.spacing.xs,
    width: 190,
  },
  root: { backgroundColor: ui.colors.appBackground, flex: 1 },
  tab: { alignItems: "center", flex: 1, gap: 2, justifyContent: "center", minHeight: 58 },
  tabIcon: { color: ui.colors.textSoft, fontSize: 22, fontWeight: "800", lineHeight: 24 },
  tabIconActive: { color: "#5067f6" },
  tabLabel: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "700" },
  tabLabelActive: { color: "#5067f6" },
  topSide: { height: 38, width: 38 },
  topBar: {
    alignItems: "center",
    backgroundColor: ui.colors.appBackground,
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    flexDirection: "row",
    minHeight: PROJECT_TOP_BAR_HEIGHT,
    paddingHorizontal: ui.spacing.screenX,
    paddingVertical: ui.spacing.sm,
  },
})
