import type { ReactNode } from "react"
import { ScrollView, StyleSheet, View } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import { ui } from "../constants/ui"

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  if (!scroll) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.body}>{children}</View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: ui.colors.appBackground },
  body: {
    flexGrow: 1,
    gap: ui.spacing.xl,
    paddingHorizontal: ui.spacing.screenX,
    paddingVertical: ui.spacing.xl,
  },
})
