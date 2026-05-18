import { StyleSheet, Text, View } from "react-native"

export function EmptyState({ title }: { title: string }) {
  return (
    <View style={styles.root}>
      <Text style={styles.title}>{title}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { paddingVertical: 24 },
  title: { color: "#475569", fontSize: 15, textAlign: "center" },
})
