export const VIRTUAL_STUDY_REVIEW_PROJECT_ID = "guide-virtual-study-review"
export const VIRTUAL_STUDY_REVIEW_SUBJECT_ID = "guide-virtual-study-review-subject"
export const VIRTUAL_STUDY_REVIEW_SUBJECT_PROJECT_ID = "guide-virtual-study-review-subject-project"
export const VIRTUAL_STUDY_REVIEW_MATERIAL_ID = "guide-virtual-study-review-material"

export function isVirtualStudyReviewProjectId(projectId: string | null | undefined) {
  return projectId === VIRTUAL_STUDY_REVIEW_PROJECT_ID
}

