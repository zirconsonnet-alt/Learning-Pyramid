import { router } from "expo-router"

import { useAuth } from "../auth/AuthProvider"
import { MineScreen } from "../screens/MineScreen"

export default function MineRoute() {
  const auth = useAuth()

  return <MineScreen openGlobalSettings={() => router.push("/settings/global")} signOut={() => void auth.signOut()} />
}
