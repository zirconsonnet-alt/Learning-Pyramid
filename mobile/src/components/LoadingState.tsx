import { ActivityIndicator, StyleSheet, Text, View } from "react-native"

export function LoadingState({ label = "加载中" }: { label?: string }) {
  return (
    <View style={styles.root}>
      <ActivityIndicator />
      <Text style={styles.text}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { alignItems: "center", gap: 10, padding: 24 },
  text: { color: "#475569", fontSize: 14 },
})
