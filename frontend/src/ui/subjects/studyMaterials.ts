import type { StudyMaterialType } from "@/ui/api/subjects"

export function formatStudyMaterialTypeLabel(materialType: StudyMaterialType) {
  if (materialType === "COURSE") return "网课"
  if (materialType === "BOOK") return "书本"
  return "零散知识"
}

export function describeStudyMaterialHint(materialType: StudyMaterialType) {
  if (materialType === "BOOK") return "创建后会直接进入项目设置，你可以空白开始、粘贴目录，或稍后补一键复用网课树。"
  if (materialType === "LOOSE_POINTS") return "适合临时知识、补充例题和碎片整理。"
  return "适合视频课、直播回放和章节式课程。"
}
