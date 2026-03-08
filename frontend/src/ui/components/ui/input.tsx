import * as React from "react"

import { cn } from "@/ui/utils"

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-xl border border-input/90 bg-white/90 px-4 py-2 text-sm shadow-[0_8px_22px_-18px_rgba(15,23,42,0.25)] transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500",
        className,
      )}
      ref={ref}
      {...props}
    />
  )
})
Input.displayName = "Input"
