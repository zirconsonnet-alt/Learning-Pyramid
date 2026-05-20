import { StyleSheet, Text, View } from "react-native"

import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"
import type { LocalCoursePackage } from "../offlineCoursePackages/schema"

export function OfflineCoursePackagesScreen({
  connectComputer,
  packages,
  projectTitle,
}: {
  connectComputer: () => void
  packages: LocalCoursePackage[]
  projectTitle?: string | null
}) {
  return (
    <Screen>
      <View style={styles.header}>
        <Text maxFontSizeMultiplier={1.1} style={styles.title}>离线课程包</Text>
        <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{projectTitle ?? "当前项目"}</Text>
      </View>
      <AppButton label="连接电脑" onPress={connectComputer} />
      {packages.length === 0 ? <EmptyState title="暂无离线课程包" /> : null}
      <View style={styles.list}>
        {packages.map((item) => (
          <View key={item.packageId} style={styles.row}>
            <Text maxFontSizeMultiplier={1.1} style={styles.rowTitle}>{item.title}</Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{item.status}</Text>
          </View>
        ))}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: ui.spacing.xs },
  list: { gap: 0 },
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  row: { borderBottomColor: ui.colors.borderSoft, borderBottomWidth: 1, gap: ui.spacing.xs, paddingVertical: ui.spacing.lg },
  rowTitle: { color: ui.colors.text, fontSize: ui.type.body, fontWeight: "700" },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
