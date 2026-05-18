import { StyleSheet, TextInput, type TextInputProps } from "react-native"

export function AppTextInput(props: TextInputProps) {
  return <TextInput placeholderTextColor="#94a3b8" {...props} style={[styles.input, props.style]} />
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: "#ffffff",
    borderColor: "#cbd5e1",
    borderRadius: 8,
    borderWidth: 1,
    color: "#0f172a",
    fontSize: 16,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
})
