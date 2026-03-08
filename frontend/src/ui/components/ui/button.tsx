import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/ui/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:shadow-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[0_14px_28px_-18px_rgba(30,58,95,0.72)] hover:-translate-y-px hover:bg-[hsl(213_52%_21%)] disabled:bg-slate-300 disabled:text-slate-500",
        secondary:
          "bg-secondary text-secondary-foreground border border-border/60 hover:bg-secondary/80 disabled:bg-slate-200 disabled:text-slate-500",
        outline:
          "border border-input bg-white/90 text-[#486284] shadow-[0_10px_24px_-20px_rgba(15,23,42,0.25)] hover:border-primary/20 hover:bg-accent hover:text-foreground disabled:border-border/70 disabled:bg-white/60 disabled:text-muted-foreground",
        ghost: "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
        destructive: "bg-destructive text-destructive-foreground shadow-[0_14px_28px_-18px_rgba(220,38,38,0.45)] hover:bg-destructive/90",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-6",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  },
)
Button.displayName = "Button"
