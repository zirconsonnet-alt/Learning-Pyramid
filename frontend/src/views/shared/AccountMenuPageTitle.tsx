type AccountMenuPageTitleProps = {
  eyebrow: string
  title: string
  titleAs?: "div" | "h1" | "h2" | "h3"
}

export function AccountMenuPageTitle(props: AccountMenuPageTitleProps) {
  const { eyebrow, title, titleAs: Title = "div" } = props

  return (
    <div className="space-y-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--theme-subtle-text)]">{eyebrow}</div>
      <Title className="text-2xl font-semibold tracking-tight text-foreground">{title}</Title>
    </div>
  )
}
