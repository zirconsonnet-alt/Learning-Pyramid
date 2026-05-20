import { StyleSheet, Text, View } from "react-native"

import { AppButton } from "../components/AppButton"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

const ACCOUNT_ITEMS = ["个人中心", "好友中心", "会员中心"]
const SYSTEM_ITEMS = ["用户指南", "后台管理"]

export function MineScreen({
  openGlobalSettings,
  signOut,
}: {
  openGlobalSettings: () => void
  signOut: () => void
}) {
  return (
    <Screen>
      <Text maxFontSizeMultiplier={1.1} style={styles.title}>
        我的
      </Text>

      <View style={styles.section}>
        {ACCOUNT_ITEMS.map((label) => (
          <Text key={label} maxFontSizeMultiplier={1.1} style={styles.item}>
            {label}
          </Text>
        ))}
      </View>

      <View style={styles.section}>
        {SYSTEM_ITEMS.map((label) => (
          <Text key={label} maxFontSizeMultiplier={1.1} style={styles.item}>
            {label}
          </Text>
        ))}
        <AppButton label="全局设置" onPress={openGlobalSettings} variant="secondary" />
      </View>

      <AppButton label="退出登录" onPress={signOut} variant="secondary" />
    </Screen>
  )
}

const styles = StyleSheet.create({
  item: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    color: ui.colors.text,
    fontSize: ui.type.body,
    paddingVertical: ui.spacing.lg,
  },
  section: { gap: 0 },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
