import { Suspense, lazy } from "react"
import type { ReactNode } from "react"
import { createBrowserRouter, Navigate } from "react-router-dom"

import { AppShell } from "@/shell/AppShell"
import { RouteErrorPage } from "@/views/system/RouteErrorPage"
import { RoutePendingPage } from "@/views/system/RoutePendingPage"
import { PomodoroWorkbenchGate } from "@/views/pomodoro/PomodoroWorkbenchGate"

const AuthPage = lazy(async () => ({ default: (await import("@/views/auth/AuthPage")).AuthPage }))
const HomePage = lazy(async () => ({ default: (await import("@/views/home/HomePage")).HomePage }))
const GuidePage = lazy(async () => ({ default: (await import("@/views/guide/GuidePage")).GuidePage }))
const InstancePage = lazy(async () => ({ default: (await import("@/views/instances/InstancePage")).InstancePage }))
const ConvergencePage = lazy(async () => ({ default: (await import("@/views/convergences/ConvergencePage")).ConvergencePage }))
const AdminPage = lazy(async () => ({ default: (await import("@/views/admin/AdminPage")).AdminPage }))
const AdminMembershipPage = lazy(async () => ({ default: (await import("@/views/admin/AdminMembershipPage")).AdminMembershipPage }))
const AdminUserDetailPage = lazy(async () => ({ default: (await import("@/views/admin/AdminUserDetailPage")).AdminUserDetailPage }))
const AdminUsersPage = lazy(async () => ({ default: (await import("@/views/admin/AdminUsersPage")).AdminUsersPage }))
const FriendsPage = lazy(async () => ({ default: (await import("@/views/friends/FriendsPage")).FriendsPage }))
const AiChatPage = lazy(async () => ({ default: (await import("@/views/ai/AiChatPage")).AiChatPage }))
const LearningObjectNodePage = lazy(async () => ({
  default: (await import("@/views/learningObjects/LearningObjectNodePage")).LearningObjectNodePage,
}))
const LearningTaskNodePage = lazy(async () => ({
  default: (await import("@/views/learningTasks/LearningTaskNodePage")).LearningTaskNodePage,
}))
const MembershipPage = lazy(async () => ({ default: (await import("@/views/membership/MembershipPage")).MembershipPage }))
const ProjectsPage = lazy(async () => ({ default: (await import("@/views/projects/ProjectsPage")).ProjectsPage }))
const ProfilePage = lazy(async () => ({ default: (await import("@/views/profile/ProfilePage")).ProfilePage }))
const RecallPointPage = lazy(async () => ({ default: (await import("@/views/recallPoints/RecallPointPage")).RecallPointPage }))
const ReviewRecommendationsPage = lazy(async () => ({
  default: (await import("@/views/recommendations/ReviewRecommendationsPage")).ReviewRecommendationsPage,
}))
const ReviewChainPage = lazy(async () => ({ default: (await import("@/views/reviewChains/ReviewChainPage")).ReviewChainPage }))
const ReviewTaskPage = lazy(async () => ({ default: (await import("@/views/reviewTasks/ReviewTaskPage")).ReviewTaskPage }))
const ProjectSettingsPage = lazy(async () => ({ default: (await import("@/views/settings/ProjectSettingsPage")).ProjectSettingsPage }))
const GlobalSettingsPage = lazy(async () => ({ default: (await import("@/views/settings/GlobalSettingsPage")).GlobalSettingsPage }))
const SubtitleToolPage = lazy(async () => ({ default: (await import("@/views/subtitleTool/SubtitleToolPage")).SubtitleToolPage }))
const ObjectTreePage = lazy(async () => ({ default: (await import("@/views/trees/ObjectTreePage")).ObjectTreePage }))
const TaskTreePage = lazy(async () => ({ default: (await import("@/views/trees/TaskTreePage")).TaskTreePage }))
const WorkbenchPage = lazy(async () => ({ default: (await import("@/views/workbench/WorkbenchPage")).WorkbenchPage }))
const PomodoroPage = lazy(async () => ({ default: (await import("@/views/pomodoro/PomodoroPage")).PomodoroPage }))

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
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/docs", element: <Navigate to="/guide" replace /> },
      { path: "/guide", element: lazyElement(<GuidePage />) },
      { path: "/projects", element: lazyElement(<ProjectsPage />) },
      { path: "/friends", element: lazyElement(<FriendsPage />) },
      { path: "/groups", element: <Navigate to="/friends" replace /> },
      { path: "/groups/:groupId", element: <Navigate to="/friends" replace /> },
      { path: "/membership", element: lazyElement(<MembershipPage />) },
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
      { path: "/p/:projectId/pomodoro", element: <Navigate to="/pomodoro" replace /> },
      { path: "/p/:projectId/recommended-reviews", element: lazyElement(<ReviewRecommendationsPage />) },
      { path: "/p/:projectId/settings", element: lazyElement(<ProjectSettingsPage />) },
      { path: "/p/:projectId/ai-chat", element: lazyElement(<AiChatPage />) },
      { path: "/p/:projectId/task-tree", element: lazyElement(<TaskTreePage />) },
      { path: "/p/:projectId/learning-task-nodes/:nodeId", element: lazyElement(<LearningTaskNodePage />) },
      { path: "/p/:projectId/learning-object-nodes/:nodeId", element: lazyElement(<LearningObjectNodePage />) },
      { path: "/p/:projectId/instances/:instanceId", element: lazyElement(<InstancePage />) },
      { path: "/p/:projectId/object-tree", element: lazyElement(<ObjectTreePage />) },
      { path: "/p/:projectId/review-chains/:reviewChainId", element: lazyElement(<ReviewChainPage />) },
      { path: "/p/:projectId/convergences/:convergenceId", element: lazyElement(<ConvergencePage />) },
      { path: "/p/:projectId/review-tasks/:reviewTaskId", element: lazyElement(<ReviewTaskPage />) },
      { path: "/p/:projectId/recall-points/:recallPointId", element: lazyElement(<RecallPointPage />) },
    ],
  },
])
