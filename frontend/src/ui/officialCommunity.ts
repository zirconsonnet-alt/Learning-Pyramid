const OFFICIAL_COMMUNITY_GROUP_NUMBER = "1082065706"
const OFFICIAL_COMMUNITY_CONTACT_QQ = "3125049051"

export function getOfficialCommunityHeadline() {
  return "官方群反馈"
}

export function getOfficialCommunityDescription() {
  return "产品反馈、问题答疑和版本通知都放在官方群里。"
}

export function getOfficialCommunityDetailText() {
  const groupNumber = OFFICIAL_COMMUNITY_GROUP_NUMBER.trim()
  if (groupNumber) return `官方群号：${groupNumber}`
  return `暂未公开群号，可先联系群主 QQ ${OFFICIAL_COMMUNITY_CONTACT_QQ} 申请入群。`
}

export function getOfficialCommunityCopyValue() {
  const groupNumber = OFFICIAL_COMMUNITY_GROUP_NUMBER.trim()
  if (groupNumber) return groupNumber
  return OFFICIAL_COMMUNITY_CONTACT_QQ
}

export function getOfficialCommunityCopyLabel() {
  return OFFICIAL_COMMUNITY_GROUP_NUMBER.trim() ? "复制群号" : "复制群主 QQ"
}

export function getOfficialCommunityCopySuccessTitle() {
  return OFFICIAL_COMMUNITY_GROUP_NUMBER.trim() ? "官方群号已复制" : "群主 QQ 已复制"
}

export function getOfficialCommunityCopySuccessMessage() {
  const value = getOfficialCommunityCopyValue()
  return OFFICIAL_COMMUNITY_GROUP_NUMBER.trim()
    ? `官方群号 ${value} 已复制到剪贴板。`
    : `群主 QQ ${value} 已复制到剪贴板，可先联系申请入群。`
}
