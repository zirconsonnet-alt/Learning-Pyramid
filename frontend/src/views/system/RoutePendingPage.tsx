export function RoutePendingPage() {
  return (
    <div className="container py-10">
      <div className="theme-status-surface flex items-center gap-4 px-6 py-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_36px_-24px_rgba(30,58,95,0.72)]" />
        <div>
          <p className="text-sm font-medium text-foreground">正在加载页面</p>
          <p className="text-sm text-muted-foreground">准备当前工作区的界面与上下文。</p>
        </div>
      </div>
    </div>
  )
}
