import { ActivityIndicator, StyleSheet, Text, View } from "react-native"

import { ui } from "../constants/ui"

export function LoadingState({ label = "加载中" }: { label?: string }) {
  return (
    <View style={styles.root}>
      <ActivityIndicator />
      <Text style={styles.text}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { alignItems: "center", gap: ui.spacing.md, padding: 24 },
  text: { color: ui.colors.textMuted, fontSize: 14 },
})
