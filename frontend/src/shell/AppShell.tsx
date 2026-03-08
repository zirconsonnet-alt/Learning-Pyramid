import { Link, Outlet, useParams } from "react-router-dom"

import { MainNav } from "@/shell/MainNav"
import { useProject } from "@/ui/queries/projects"

export function AppShell() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const { projectTitle } = useProject(pid)

  return (
    <div className="min-h-dvh">
      <header className="border-b border-border/70 bg-white/88 shadow-[0_10px_28px_-24px_rgba(15,23,42,0.4)] backdrop-blur-xl supports-[backdrop-filter]:bg-white/78">
        <div className="container flex flex-col gap-3 py-4 lg:flex-row lg:items-center">
          <div className="flex min-w-0 items-center gap-3">
            <Link to="/projects" className="shrink-0 text-lg font-semibold tracking-tight text-primary hover:text-primary/80">
              LearningPyramid
            </Link>
            {pid ? (
              <>
                <span className="text-sm text-muted-foreground">/</span>
                <div className="theme-meta min-w-0 max-w-[16rem] truncate">{projectTitle || pid}</div>
              </>
            ) : null}
          </div>
          <MainNav />
        </div>
      </header>
      <main className="container py-8">
        <Outlet />
      </main>
    </div>
  )
}
