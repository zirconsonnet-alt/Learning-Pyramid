import { createBrowserRouter, Navigate } from "react-router-dom"

import { AppShell } from "@/shell/AppShell"
import { GuidePage } from "@/views/guide/GuidePage"
import { InstancePage } from "@/views/instances/InstancePage"
import { LearningObjectNodePage } from "@/views/learningObjects/LearningObjectNodePage"
import { LearningTaskNodePage } from "@/views/learningTasks/LearningTaskNodePage"
import { ProjectsPage } from "@/views/projects/ProjectsPage"
import { RecallPointPage } from "@/views/recallPoints/RecallPointPage"
import { LearningTaskPage } from "@/views/learningTasks/LearningTaskPage"
import { ReviewChainPage } from "@/views/reviewChains/ReviewChainPage"
import { ProjectSettingsPage } from "@/views/settings/ProjectSettingsPage"
import { RouteErrorPage } from "@/views/system/RouteErrorPage"
import { TimelinePage } from "@/views/timeline/TimelinePage"
import { ObjectTreePage } from "@/views/trees/ObjectTreePage"
import { TaskTreePage } from "@/views/trees/TaskTreePage"
import { WorkbenchPage } from "@/views/workbench/WorkbenchPage"

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/", element: <Navigate to="/projects" replace /> },
      { path: "/docs", element: <Navigate to="/guide" replace /> },
      { path: "/guide", element: <GuidePage /> },
      { path: "/projects", element: <ProjectsPage /> },
      { path: "/p/:projectId/workbench", element: <WorkbenchPage /> },
      { path: "/p/:projectId/settings", element: <ProjectSettingsPage /> },
      { path: "/p/:projectId/timeline", element: <TimelinePage /> },
      { path: "/p/:projectId/task-tree", element: <TaskTreePage /> },
      { path: "/p/:projectId/learning-tasks/:learningTaskId", element: <LearningTaskPage /> },
      { path: "/p/:projectId/learning-task-nodes/:nodeId", element: <LearningTaskNodePage /> },
      { path: "/p/:projectId/learning-object-nodes/:nodeId", element: <LearningObjectNodePage /> },
      { path: "/p/:projectId/instances/:instanceId", element: <InstancePage /> },
      { path: "/p/:projectId/object-tree", element: <ObjectTreePage /> },
      { path: "/p/:projectId/review-chains/:reviewChainId", element: <ReviewChainPage /> },
      { path: "/p/:projectId/recall-points/:recallPointId", element: <RecallPointPage /> },
    ],
  },
])
