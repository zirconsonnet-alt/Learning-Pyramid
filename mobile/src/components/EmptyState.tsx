import { StyleSheet, Text, View } from "react-native"

import { ui } from "../constants/ui"

export function EmptyState({ title }: { title: string }) {
  return (
    <View style={styles.root}>
      <Text style={styles.title}>{title}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { paddingVertical: 24 },
  title: { color: ui.colors.textMuted, fontSize: ui.type.control, textAlign: "center" },
})
