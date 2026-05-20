import { useLocalSearchParams } from "expo-router"

import { firstRouteParam } from "../../../routing/params"
import { OfflineCoursePackagesScreen } from "../../../screens/OfflineCoursePackagesScreen"

export default function OfflinePackagesRoute() {
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""

  return (
    <OfflineCoursePackagesScreen
      connectComputer={() => {
        throw new Error(`扫码连接电脑尚未接入：${subjectId}/${scopedProjectId}`)
      }}
      packages={[]}
      projectTitle={scopedProjectId}
    />
  )
}
