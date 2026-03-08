import { isRouteErrorResponse, useRouteError } from "react-router-dom"

export function RouteErrorPage() {
  const err = useRouteError()

  let title = "应用程序出现意外错误"
  let detail = ""

  if (isRouteErrorResponse(err)) {
    title = `页面加载失败（${err.status}）`
    detail = err.statusText
  } else if (err instanceof Error) {
    detail = err.message
  } else {
    detail = String(err)
  }

  return (
    <div className="container py-10">
      <div className="rounded-lg border p-6">
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
        <p className="mt-4 text-sm text-muted-foreground">你可以返回“项目”页面重新进入。</p>
      </div>
    </div>
  )
}

