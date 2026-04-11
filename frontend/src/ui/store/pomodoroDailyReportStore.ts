import { create } from "zustand"
import { persist } from "zustand/middleware"

export type DailyReportDirection = "progress" | "flat" | "regress" | ""

export type PomodoroDailyReport = {
  dateKey: string
  direction: DailyReportDirection
  focusScore: number
  summary: string
  adjustment: string
  updatedAt: number | null
}

type PomodoroDailyReportState = {
  reportsByDate: Record<string, PomodoroDailyReport>
  getReport: (dateKey: string) => PomodoroDailyReport
  updateReport: (dateKey: string, patch: Partial<Omit<PomodoroDailyReport, "dateKey" | "updatedAt">>) => void
  reset: () => void
}

function createEmptyReport(dateKey: string): PomodoroDailyReport {
  return {
    dateKey,
    direction: "",
    focusScore: 0,
    summary: "",
    adjustment: "",
    updatedAt: null,
  }
}

function normalizeReport(dateKey: string, report: PomodoroDailyReport | undefined): PomodoroDailyReport {
  if (!report) return createEmptyReport(dateKey)
  const direction = ["progress", "flat", "regress", ""].includes(report.direction) ? report.direction : ""
  return {
    dateKey,
    direction: direction as DailyReportDirection,
    focusScore: Number.isFinite(report.focusScore) ? Math.max(0, Math.min(5, Math.round(report.focusScore))) : 0,
    summary: String(report.summary ?? "").slice(0, 800),
    adjustment: String(report.adjustment ?? "").slice(0, 500),
    updatedAt: typeof report.updatedAt === "number" && Number.isFinite(report.updatedAt) ? report.updatedAt : null,
  }
}

const initialState = {
  reportsByDate: {} as Record<string, PomodoroDailyReport>,
}

export const usePomodoroDailyReportStore = create<PomodoroDailyReportState>()(
  persist(
    (set, get) => ({
      ...initialState,
      getReport: (dateKey) => normalizeReport(dateKey, get().reportsByDate[dateKey]),
      updateReport: (dateKey, patch) =>
        set((state) => {
          const current = normalizeReport(dateKey, state.reportsByDate[dateKey])
          const next = normalizeReport(dateKey, {
            ...current,
            ...patch,
            dateKey,
            updatedAt: Date.now(),
          })
          return {
            ...state,
            reportsByDate: {
              ...state.reportsByDate,
              [dateKey]: next,
            },
          }
        }),
      reset: () => set(initialState),
    }),
    {
      name: "plm-pomodoro-daily-reports",
      version: 1,
    },
  ),
)
