import React from "react"

export function DevtoolsSlot() {
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
