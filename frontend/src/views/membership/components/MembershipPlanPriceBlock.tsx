import type { ReactNode } from "react"

import { cn } from "@/ui/utils"

type MembershipPlanPriceBlockProps = {
  title: string
  price: string
  unit: string
  note: string
  accent?: boolean
  className?: string
  children?: ReactNode
}

export function MembershipPlanPriceBlock(props: MembershipPlanPriceBlockProps) {
  const { title, price, unit, note, accent = false, className, children } = props

  return (
    <div className={cn("lp-showcase-membership-price-block", accent && "lp-showcase-membership-price-block-accent", className)}>
      <h3>{title}</h3>
      <div className="lp-showcase-price">
        <strong>{price}</strong>
        <span>{unit}</span>
      </div>
      <p className="lp-showcase-membership-plan-note">{note}</p>
      {children}
    </div>
  )
}
