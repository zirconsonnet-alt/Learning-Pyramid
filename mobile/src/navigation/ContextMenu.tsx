import { router } from "expo-router"
import { Modal, Pressable, StyleSheet, Text, View } from "react-native"

import { ui } from "../constants/ui"
import { buildContextMenuItems, getLearningContextStatus, type ContextMenuItem, type LearningContextInput } from "./mobileNavigation"

export function ContextMenu({
  context,
  onDismiss,
  visible,
}: {
  context: LearningContextInput
  onDismiss: () => void
  visible: boolean
}) {
  const items = buildContextMenuItems(context)
  const byId = new Map(items.map((item) => [item.id, item]))
  const status = getLearningContextStatus(context)

  return (
    <Modal animationType="slide" onRequestClose={onDismiss} transparent visible={visible}>
      <Pressable accessibilityRole="button" onPress={onDismiss} style={styles.scrim} />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <Text maxFontSizeMultiplier={1.1} style={styles.sheetTitle}>
          {status === "no-subject" || status === "invalid" ? "学习空间尚未配置" : "当前上下文"}
        </Text>

        {status === "no-subject" || status === "invalid" ? (
          <View style={styles.group}>
            <Text maxFontSizeMultiplier={1.1} style={styles.groupTitle}>学科</Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.currentText}>暂无学科</Text>
            <ActionButton item={byId.get("select-subject")} onDismiss={onDismiss} />
          </View>
        ) : (
          <>
            <View style={styles.group}>
              <Text maxFontSizeMultiplier={1.1} style={styles.groupTitle}>学科</Text>
              <Text maxFontSizeMultiplier={1.1} numberOfLines={1} style={styles.currentText}>
                {context.subjectTitle || context.subjectId}
              </Text>
              <View style={styles.actionRow}>
                <ActionButton item={byId.get("switch-subject")} onDismiss={onDismiss} />
                <ActionButton item={byId.get("subject-settings")} onDismiss={onDismiss} />
              </View>
            </View>

            <View style={styles.group}>
              <Text maxFontSizeMultiplier={1.1} style={styles.groupTitle}>项目</Text>
              <Text maxFontSizeMultiplier={1.1} numberOfLines={1} style={styles.currentText}>
                {status === "project" ? context.projectTitle || context.scopedProjectId : "暂无项目"}
              </Text>
              <View style={styles.actionRow}>
                <ActionButton item={byId.get(status === "project" ? "switch-project" : "select-project")} onDismiss={onDismiss} />
                {status === "project" ? <ActionButton item={byId.get("project-settings")} onDismiss={onDismiss} /> : null}
              </View>
            </View>

            <View style={styles.group}>
              <Text maxFontSizeMultiplier={1.1} style={styles.groupTitle}>管理</Text>
              <View style={styles.actionRow}>
                <ActionButton item={byId.get("subject-center")} onDismiss={onDismiss} />
                {status === "project" ? <ActionButton item={byId.get("project-center")} onDismiss={onDismiss} /> : null}
              </View>
            </View>
          </>
        )}
      </View>
    </Modal>
  )
}

function ActionButton({ item, onDismiss }: { item?: ContextMenuItem; onDismiss: () => void }) {
  if (!item) return null

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => {
        onDismiss()
        if (!item.target) return
        router.push({ pathname: item.target.pathname as never, params: item.target.params as never })
      }}
      style={styles.actionButton}
    >
      <Text maxFontSizeMultiplier={1.1} style={styles.actionText}>
        {item.label}
      </Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  actionButton: {
    alignItems: "center",
    backgroundColor: ui.colors.secondaryBackground,
    borderColor: ui.colors.border,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    flex: 1,
    justifyContent: "center",
    minHeight: 38,
    paddingHorizontal: ui.spacing.md,
    paddingVertical: ui.spacing.sm,
  },
  actionRow: { flexDirection: "row", gap: ui.spacing.sm },
  actionText: { color: ui.colors.secondaryText, fontSize: ui.type.control, fontWeight: "700" },
  currentText: { color: ui.colors.text, fontSize: ui.type.body, fontWeight: "800" },
  group: { gap: ui.spacing.sm },
  groupTitle: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "700" },
  handle: {
    alignSelf: "center",
    backgroundColor: ui.colors.border,
    borderRadius: 999,
    height: 4,
    width: 36,
  },
  scrim: {
    backgroundColor: "rgba(17, 24, 39, 0.28)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  sheet: {
    backgroundColor: ui.colors.surface,
    borderTopLeftRadius: ui.radius.xl,
    borderTopRightRadius: ui.radius.xl,
    bottom: 0,
    gap: ui.spacing.lg,
    left: 0,
    paddingBottom: ui.spacing.xl,
    paddingHorizontal: ui.spacing.screenX,
    paddingTop: ui.spacing.md,
    position: "absolute",
    right: 0,
  },
  sheetTitle: { color: ui.colors.text, fontSize: ui.type.sectionTitle, fontWeight: "800" },
})
