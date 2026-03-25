import { Suspense, lazy } from "react"
import type { ReactNode } from "react"
import { createBrowserRouter, Navigate } from "react-router-dom"

import { AppShell } from "@/shell/AppShell"
import { RouteErrorPage } from "@/views/system/RouteErrorPage"
import { RoutePendingPage } from "@/views/system/RoutePendingPage"

const AuthPage = lazy(async () => ({ default: (await import("@/views/auth/AuthPage")).AuthPage }))
const GuidePage = lazy(async () => ({ default: (await import("@/views/guide/GuidePage")).GuidePage }))
const InstancePage = lazy(async () => ({ default: (await import("@/views/instances/InstancePage")).InstancePage }))
const ConvergencePage = lazy(async () => ({ default: (await import("@/views/convergences/ConvergencePage")).ConvergencePage }))
const AdminPage = lazy(async () => ({ default: (await import("@/views/admin/AdminPage")).AdminPage }))
const AdminGroupsPage = lazy(async () => ({ default: (await import("@/views/admin/AdminGroupsPage")).AdminGroupsPage }))
const AdminGroupDetailPage = lazy(async () => ({ default: (await import("@/views/admin/AdminGroupDetailPage")).AdminGroupDetailPage }))
const AdminUserDetailPage = lazy(async () => ({ default: (await import("@/views/admin/AdminUserDetailPage")).AdminUserDetailPage }))
const AdminUsersPage = lazy(async () => ({ default: (await import("@/views/admin/AdminUsersPage")).AdminUsersPage }))
const GroupDetailPage = lazy(async () => ({ default: (await import("@/views/groups/GroupDetailPage")).GroupDetailPage }))
const LearningObjectNodePage = lazy(async () => ({
  default: (await import("@/views/learningObjects/LearningObjectNodePage")).LearningObjectNodePage,
}))
const LearningTaskNodePage = lazy(async () => ({
  default: (await import("@/views/learningTasks/LearningTaskNodePage")).LearningTaskNodePage,
}))
const GroupsPage = lazy(async () => ({ default: (await import("@/views/groups/GroupsPage")).GroupsPage }))
const ProjectsPage = lazy(async () => ({ default: (await import("@/views/projects/ProjectsPage")).ProjectsPage }))
const ProfilePage = lazy(async () => ({ default: (await import("@/views/profile/ProfilePage")).ProfilePage }))
const RecallPointPage = lazy(async () => ({ default: (await import("@/views/recallPoints/RecallPointPage")).RecallPointPage }))
const ReviewChainPage = lazy(async () => ({ default: (await import("@/views/reviewChains/ReviewChainPage")).ReviewChainPage }))
const ReviewTaskPage = lazy(async () => ({ default: (await import("@/views/reviewTasks/ReviewTaskPage")).ReviewTaskPage }))
const ProjectSettingsPage = lazy(async () => ({ default: (await import("@/views/settings/ProjectSettingsPage")).ProjectSettingsPage }))
const ObjectTreePage = lazy(async () => ({ default: (await import("@/views/trees/ObjectTreePage")).ObjectTreePage }))
const TaskTreePage = lazy(async () => ({ default: (await import("@/views/trees/TaskTreePage")).TaskTreePage }))
const WorkbenchPage = lazy(async () => ({ default: (await import("@/views/workbench/WorkbenchPage")).WorkbenchPage }))

function lazyElement(element: ReactNode) {
  return <Suspense fallback={<RoutePendingPage />}>{element}</Suspense>
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: lazyElement(<AuthPage />),
    errorElement: <RouteErrorPage />,
  },
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/", element: <Navigate to="/projects" replace /> },
      { path: "/docs", element: <Navigate to="/guide" replace /> },
      { path: "/guide", element: lazyElement(<GuidePage />) },
      { path: "/projects", element: lazyElement(<ProjectsPage />) },
      { path: "/groups", element: lazyElement(<GroupsPage />) },
      { path: "/groups/:groupId", element: lazyElement(<GroupDetailPage />) },
      { path: "/profile", element: lazyElement(<ProfilePage />) },
      { path: "/admin", element: lazyElement(<AdminPage />) },
      { path: "/admin/users", element: lazyElement(<AdminUsersPage />) },
      { path: "/admin/groups", element: lazyElement(<AdminGroupsPage />) },
      { path: "/admin/groups/:groupId", element: lazyElement(<AdminGroupDetailPage />) },
      { path: "/admin/users/:userId", element: lazyElement(<AdminUserDetailPage />) },
      { path: "/p/:projectId/workbench", element: lazyElement(<WorkbenchPage />) },
      { path: "/p/:projectId/settings", element: lazyElement(<ProjectSettingsPage />) },
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
