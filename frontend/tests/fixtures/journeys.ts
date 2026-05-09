export const journeyIds = {
  appLoad: "app-load",
  mainNavigation: "main-navigation",
  subjectProjectEntry: "subject-project-entry",
  workbench: "workbench",
  review: "review",
  pomodoro: "pomodoro",
  settings: "settings",
  auth: "auth",
  membership: "membership",
  admin: "admin",
  mediaUpload: "media-upload",
  aiChat: "ai-chat",
} as const

export const requiredJourneyIds = Object.values(journeyIds)
