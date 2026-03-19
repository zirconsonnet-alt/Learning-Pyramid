import "@/index.css"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React from "react"
import ReactDOM from "react-dom/client"
import { RouterProvider } from "react-router-dom"

import { DevtoolsSlot } from "@/DevtoolsSlot"
import { router } from "@/router"
import { FeedbackViewport } from "@/ui/components/FeedbackViewport"
import { ThemeController } from "@/ui/theme/ThemeController"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnReconnect: true,
      refetchOnWindowFocus: true,
    },
  },
})

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeController />
      <RouterProvider router={router} />
      <FeedbackViewport />
      <DevtoolsSlot />
    </QueryClientProvider>
  </React.StrictMode>,
)
