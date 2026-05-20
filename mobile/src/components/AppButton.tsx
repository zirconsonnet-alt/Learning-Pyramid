import { Pressable, StyleSheet, Text, type StyleProp, type ViewStyle } from "react-native"

import { ui } from "../constants/ui"

export function AppButton({
  label,
  onPress,
  disabled = false,
  style,
  variant = "primary",
}: {
  label: string
  onPress: () => void
  disabled?: boolean
  style?: StyleProp<ViewStyle>
  variant?: "primary" | "secondary"
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.root, variant === "secondary" && styles.secondary, style, disabled && styles.disabled]}
    >
      <Text maxFontSizeMultiplier={1.1} style={[styles.label, variant === "secondary" && styles.secondaryLabel]}>
        {label}
      </Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  root: {
    alignItems: "center",
    backgroundColor: ui.colors.primary,
    borderRadius: ui.radius.lg,
    justifyContent: "center",
    minHeight: 44,
    paddingHorizontal: 16,
    paddingVertical: ui.spacing.md,
  },
  disabled: { opacity: 0.55 },
  label: { color: ui.colors.primaryText, fontSize: ui.type.control, fontWeight: "700" },
  secondary: {
    backgroundColor: ui.colors.secondaryBackground,
    borderColor: ui.colors.border,
    borderWidth: 1,
  },
  secondaryLabel: { color: ui.colors.secondaryText },
})
