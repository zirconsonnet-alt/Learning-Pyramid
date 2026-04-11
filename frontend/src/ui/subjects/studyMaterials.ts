import type { StudyMaterialType } from "@/ui/api/subjects"

export function formatStudyMaterialTypeLabel(materialType: StudyMaterialType) {
  if (materialType === "COURSE") return "网课"
  if (materialType === "BOOK") return "书本"
  if (materialType === "MISTAKE_BOOK") return "错题"
  return "零散知识"
}

export function describeStudyMaterialHint(materialType: StudyMaterialType) {
  if (materialType === "BOOK") return "创建后会直接进入材料设置，你可以空白开始、粘贴目录，或稍后补一键复用网课树。"
  if (materialType === "LOOSE_POINTS") return "适合临时知识、补充例题和碎片整理。"
  if (materialType === "MISTAKE_BOOK") return "适合把网课、书本和练习里的错题统一收进来，再按章节或待整理入口继续复习。"
  return "适合视频课、直播回放和章节式课程。"
}
