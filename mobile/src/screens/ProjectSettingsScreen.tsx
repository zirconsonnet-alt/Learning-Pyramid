import { StyleSheet, Text } from "react-native"

import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

export function ProjectSettingsScreen({
  openOfflinePackages,
  projectTitle,
}: {
  openOfflinePackages?: () => void
  projectTitle?: string | null
}) {
  return (
    <Screen>
      <Text maxFontSizeMultiplier={1.1} style={styles.title}>
        项目设置
      </Text>
      {openOfflinePackages ? <AppButton label="离线课程包" onPress={openOfflinePackages} variant="secondary" /> : null}
      <EmptyState title={`${projectTitle ?? "当前项目"}设置暂未开放`} />
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
