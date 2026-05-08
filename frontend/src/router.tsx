import { Suspense, lazy } from "react"
import type { ComponentType, ReactNode } from "react"
import { createBrowserRouter, Navigate } from "react-router-dom"

import { AppShell } from "@/shell/AppShell"
import { RouteErrorPage } from "@/views/system/RouteErrorPage"
import { RoutePendingPage } from "@/views/system/RoutePendingPage"
import { PomodoroWorkbenchGate } from "@/views/pomodoro/PomodoroWorkbenchGate"
import { AiChatPage } from "@/views/ai/AiChatPage"
import { ReviewRecommendationsPage } from "@/views/recommendations/ReviewRecommendationsPage"
import { ProjectSettingsPage } from "@/views/settings/ProjectSettingsPage"
import { StructureViewPage } from "@/views/trees/StructureViewPage"

const CHUNK_RELOAD_MARKER = "lp:chunk-reload-attempted"

function isStaleDynamicImportError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    message.includes("Failed to fetch dynamically imported module") ||
    message.includes("Importing a module script failed") ||
    message.includes("error loading dynamically imported module")
  )
}

async function importRouteModule<T>(loader: () => Promise<T>) {
  try {
    const mod = await loader()
    globalThis.sessionStorage?.removeItem(CHUNK_RELOAD_MARKER)
    return mod
  } catch (error) {
    if (isStaleDynamicImportError(error) && globalThis.sessionStorage?.getItem(CHUNK_RELOAD_MARKER) !== "1") {
      globalThis.sessionStorage?.setItem(CHUNK_RELOAD_MARKER, "1")
      window.location.reload()
      return new Promise<T>(() => undefined)
    }
    throw error
  }
}

function lazyRoute<TModule>(loader: () => Promise<TModule>, pick: (mod: TModule) => ComponentType) {
  return lazy(async () => ({ default: pick(await importRouteModule(loader)) }))
}

const AuthPage = lazyRoute(() => import("@/views/auth/AuthPage"), (mod) => mod.AuthPage)
const HomePage = lazyRoute(() => import("@/views/home/HomePage"), (mod) => mod.HomePage)
const GuidePage = lazyRoute(() => import("@/views/guide/GuidePage"), (mod) => mod.GuidePage)
const CreateSubjectProjectDemoPage = lazyRoute(
  () => import("@/views/guide/CreateSubjectProjectDemoPage"),
  (mod) => mod.CreateSubjectProjectDemoPage,
)
const StudyReviewDemoWorkbenchPage = lazyRoute(
  () => import("@/views/guide/StudyReviewDemoWorkbenchPage"),
  (mod) => mod.StudyReviewDemoWorkbenchPage,
)
const AiChatGuideDemoPage = lazyRoute(() => import("@/views/guide/AiChatGuideDemoPage"), (mod) => mod.AiChatGuideDemoPage)
const PomodoroGuideDemoPage = lazyRoute(() => import("@/views/guide/PomodoroGuideDemoPage"), (mod) => mod.PomodoroGuideDemoPage)
const InstancePage = lazyRoute(() => import("@/views/instances/InstancePage"), (mod) => mod.InstancePage)
const ConvergencePage = lazyRoute(() => import("@/views/convergences/ConvergencePage"), (mod) => mod.ConvergencePage)
const AdminPage = lazyRoute(() => import("@/views/admin/AdminPage"), (mod) => mod.AdminPage)
const AdminMembershipPage = lazyRoute(() => import("@/views/admin/AdminMembershipPage"), (mod) => mod.AdminMembershipPage)
const AdminUserDetailPage = lazyRoute(() => import("@/views/admin/AdminUserDetailPage"), (mod) => mod.AdminUserDetailPage)
const AdminUsersPage = lazyRoute(() => import("@/views/admin/AdminUsersPage"), (mod) => mod.AdminUsersPage)
const FriendsPage = lazyRoute(() => import("@/views/friends/FriendsPage"), (mod) => mod.FriendsPage)
const LearningObjectNodePage = lazyRoute(() => import("@/views/learningObjects/LearningObjectNodePage"), (mod) => mod.LearningObjectNodePage)
const LearningTaskNodePage = lazyRoute(() => import("@/views/learningTasks/LearningTaskNodePage"), (mod) => mod.LearningTaskNodePage)
const MembershipPage = lazyRoute(() => import("@/views/membership/MembershipPage"), (mod) => mod.MembershipPage)
const WechatPayoutBindingPage = lazyRoute(() => import("@/views/membership/WechatPayoutBindingPage"), (mod) => mod.WechatPayoutBindingPage)
const WechatWithdrawalConfirmationPage = lazyRoute(
  () => import("@/views/membership/WechatWithdrawalConfirmationPage"),
  (mod) => mod.WechatWithdrawalConfirmationPage,
)
const ProjectsPage = lazyRoute(() => import("@/views/projects/ProjectsPage"), (mod) => mod.ProjectsPage)
const ProfilePage = lazyRoute(() => import("@/views/profile/ProfilePage"), (mod) => mod.ProfilePage)
const RecallPointPage = lazyRoute(() => import("@/views/recallPoints/RecallPointPage"), (mod) => mod.RecallPointPage)
const ReviewChainPage = lazyRoute(() => import("@/views/reviewChains/ReviewChainPage"), (mod) => mod.ReviewChainPage)
const ReviewTaskPage = lazyRoute(() => import("@/views/reviewTasks/ReviewTaskPage"), (mod) => mod.ReviewTaskPage)
const GlobalSettingsPage = lazyRoute(() => import("@/views/settings/GlobalSettingsPage"), (mod) => mod.GlobalSettingsPage)
const SubtitleToolPage = lazyRoute(() => import("@/views/subtitleTool/SubtitleToolPage"), (mod) => mod.SubtitleToolPage)
const SubjectDashboardPage = lazyRoute(() => import("@/views/subjects/SubjectDashboardPage"), (mod) => mod.SubjectDashboardPage)
const WorkbenchPage = lazyRoute(() => import("@/views/workbench/WorkbenchPage"), (mod) => mod.WorkbenchPage)
const PomodoroPage = lazyRoute(() => import("@/views/pomodoro/PomodoroPage"), (mod) => mod.PomodoroPage)
const PomodoroSettingsPage = lazyRoute(() => import("@/views/pomodoro/PomodoroSettingsPage"), (mod) => mod.PomodoroSettingsPage)

function lazyElement(element: ReactNode) {
  return <Suspense fallback={<RoutePendingPage />}>{element}</Suspense>
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: lazyElement(<HomePage />),
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/home",
    element: <Navigate to="/" replace />,
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/subtitle-tool",
    element: lazyElement(<SubtitleToolPage />),
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/login",
    element: lazyElement(<AuthPage />),
    errorElement: <RouteErrorPage />,
  },
  {
    path: "/membership/wechat-payout-confirm",
    element: lazyElement(<WechatWithdrawalConfirmationPage />),
    errorElement: <RouteErrorPage />,
  },
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/docs", element: <Navigate to="/guide" replace /> },
      { path: "/guide", element: lazyElement(<GuidePage />) },
      { path: "/guide/demo/create-subject-project", element: lazyElement(<CreateSubjectProjectDemoPage />) },
      { path: "/guide/demo/study-review", element: lazyElement(<StudyReviewDemoWorkbenchPage />) },
      { path: "/guide/demo/ai-chat", element: lazyElement(<AiChatGuideDemoPage />) },
      { path: "/guide/demo/pomodoro", element: lazyElement(<PomodoroGuideDemoPage />) },
      { path: "/projects", element: lazyElement(<ProjectsPage />) },
      { path: "/subjects/:subjectId", element: lazyElement(<SubjectDashboardPage />) },
      { path: "/friends", element: lazyElement(<FriendsPage />) },
      { path: "/groups", element: <Navigate to="/friends" replace /> },
      { path: "/groups/:groupId", element: <Navigate to="/friends" replace /> },
      { path: "/membership", element: lazyElement(<MembershipPage />) },
      { path: "/membership/wechat-payout-bind", element: lazyElement(<WechatPayoutBindingPage />) },
      { path: "/profile", element: lazyElement(<ProfilePage />) },
      { path: "/settings/global", element: lazyElement(<GlobalSettingsPage />) },
      { path: "/admin", element: lazyElement(<AdminPage />) },
      { path: "/admin/membership", element: lazyElement(<AdminMembershipPage />) },
      { path: "/admin/users", element: lazyElement(<AdminUsersPage />) },
      { path: "/admin/groups", element: <Navigate to="/admin" replace /> },
      { path: "/admin/groups/:groupId", element: <Navigate to="/admin" replace /> },
      { path: "/admin/users/:userId", element: lazyElement(<AdminUserDetailPage />) },
      {
        path: "/p/:projectId/workbench",
        element: lazyElement(
          <PomodoroWorkbenchGate>
            <WorkbenchPage />
          </PomodoroWorkbenchGate>,
        ),
      },
      { path: "/pomodoro", element: lazyElement(<PomodoroPage />) },
      { path: "/pomodoro/plans/:planId", element: lazyElement(<PomodoroPage />) },
      { path: "/pomodoro/settings", element: lazyElement(<PomodoroSettingsPage />) },
      { path: "/p/:projectId/pomodoro", element: <Navigate to="/pomodoro" replace /> },
      { path: "/p/:projectId/recommended-reviews", element: lazyElement(<ReviewRecommendationsPage />) },
      { path: "/p/:projectId/settings", element: lazyElement(<ProjectSettingsPage />) },
      { path: "/p/:projectId/project-settings", element: lazyElement(<ProjectSettingsPage />) },
      { path: "/p/:projectId/ai-chat", element: lazyElement(<AiChatPage />) },
      { path: "/p/:projectId/structure-view", element: lazyElement(<StructureViewPage />) },
      { path: "/p/:projectId/learning-task-nodes/:nodeId", element: lazyElement(<LearningTaskNodePage />) },
      { path: "/p/:projectId/learning-object-nodes/:nodeId", element: lazyElement(<LearningObjectNodePage />) },
      { path: "/p/:projectId/instances/:instanceId", element: lazyElement(<InstancePage />) },
      { path: "/p/:projectId/review-chains/:reviewChainId", element: lazyElement(<ReviewChainPage />) },
      { path: "/p/:projectId/convergences/:convergenceId", element: lazyElement(<ConvergencePage />) },
      { path: "/p/:projectId/review-tasks/:reviewTaskId", element: lazyElement(<ReviewTaskPage />) },
      { path: "/p/:projectId/recall-points/:recallPointId", element: lazyElement(<RecallPointPage />) },
    ],
  },
])
