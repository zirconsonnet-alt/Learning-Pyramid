import type { StudyMaterialType } from "@/ui/api/subjects"

export function formatStudyMaterialTypeLabel(materialType: StudyMaterialType) {
  if (materialType === "COURSE") return "网课"
  if (materialType === "BOOK") return "书本"
  return "零散知识"
}

export function describeStudyMaterialHint(materialType: StudyMaterialType) {
  if (materialType === "BOOK") return "适合看书记笔记，做题"
  if (materialType === "LOOSE_POINTS") return "适合临时知识、补充例题和碎片整理。"
  return "适合视频课、直播回放和章节式课程。"
}
