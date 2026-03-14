export type DashboardTone = "slate" | "sky" | "teal" | "amber" | "rose" | "emerald"

export function dashboardToneClasses(tone: DashboardTone) {
  switch (tone) {
    case "sky":
      return { panel: "border-sky-200/80 bg-sky-50/85", icon: "bg-sky-100 text-sky-700" }
    case "teal":
      return { panel: "border-teal-200/80 bg-teal-50/85", icon: "bg-teal-100 text-teal-700" }
    case "amber":
      return { panel: "border-amber-200/80 bg-amber-50/90", icon: "bg-amber-100 text-amber-700" }
    case "rose":
      return { panel: "border-rose-200/80 bg-rose-50/90", icon: "bg-rose-100 text-rose-700" }
    case "emerald":
      return { panel: "border-emerald-200/80 bg-emerald-50/85", icon: "bg-emerald-100 text-emerald-700" }
    default:
      return { panel: "border-slate-200/80 bg-white/92", icon: "bg-slate-100 text-slate-700" }
  }
}

export function dashboardTonePillClasses(tone: DashboardTone) {
  switch (tone) {
    case "sky":
      return "border-sky-200 bg-sky-50 text-sky-700"
    case "teal":
      return "border-teal-200 bg-teal-50 text-teal-700"
    case "amber":
      return "border-amber-200 bg-amber-50 text-amber-700"
    case "rose":
      return "border-rose-200 bg-rose-50 text-rose-700"
    case "emerald":
      return "border-emerald-200 bg-emerald-50 text-emerald-700"
    default:
      return "border-slate-200 bg-slate-50 text-slate-700"
  }
}
