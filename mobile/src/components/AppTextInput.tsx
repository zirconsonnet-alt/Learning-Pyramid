import { StyleSheet, TextInput, type TextInputProps } from "react-native"

import { ui } from "../constants/ui"

export function AppTextInput(props: TextInputProps) {
  return (
    <TextInput
      maxFontSizeMultiplier={1.1}
      placeholderTextColor={ui.colors.textSoft}
      {...props}
      style={[styles.input, props.style]}
    />
  )
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.border,
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    color: ui.colors.text,
    fontSize: ui.type.body,
    minHeight: 44,
    paddingHorizontal: 12,
    paddingVertical: ui.spacing.md,
  },
})
