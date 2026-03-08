import "@/index.css"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React from "react"
import ReactDOM from "react-dom/client"
import { RouterProvider } from "react-router-dom"

import { router } from "@/router"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 0,
      refetchOnWindowFocus: false,
    },
  },
})

function DevtoolsSlot() {
  const [Devtools, setDevtools] = React.useState<React.ComponentType<{ initialIsOpen?: boolean }> | null>(null)

  React.useEffect(() => {
    if (!import.meta.env.DEV) return
    let mounted = true
    void import("@tanstack/react-query-devtools").then((mod) => {
      if (mounted) setDevtools(() => mod.ReactQueryDevtools)
    })
    return () => {
      mounted = false
    }
  }, [])

  if (!import.meta.env.DEV || Devtools === null) return null
  return <Devtools initialIsOpen={false} />
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <DevtoolsSlot />
    </QueryClientProvider>
  </React.StrictMode>,
)
