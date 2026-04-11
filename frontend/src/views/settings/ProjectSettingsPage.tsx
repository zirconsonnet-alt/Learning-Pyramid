import { type ReactNode, useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { Settings2, Sparkles, TriangleAlert } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { listRecallPointsByInstance, type Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem, RollUpStrategy } from "@/ui/api/projectConfig"
import type { ProjectType } from "@/ui/api/projects"
import type { StudyMaterial } from "@/ui/api/subjects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatMaterialReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { scanProjectDirectoryMedia, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { formatProjectTypeLabel } from "@/ui/projectTypes"
import { useMyLlmSettings, useUpdateMyLlmSettings } from "@/ui/queries/profile"
import { useProject } from "@/ui/queries/projects"
import {
  useCreateSubjectMaterial,
  useDeleteSubject,
  useDeleteSubjectMaterial,
  useEditSubject,
  useEditSubjectMaterial,
  useSubjectContext,
} from "@/ui/queries/subjects"
import { useGlobalLlmSettings, useSystemCapabilities, useUpdateGlobalLlmSettings } from "@/ui/queries/system"
import { useAppStore } from "@/ui/store/appStore"
import {
  useBulkRemapRecallPointsInstance,
  useEnsureMistakeInbox,
  useImportLearningObjectsFromBrowser,
  useInitializeBookLearningObjects,
  useInitializeBookLearningObjectsFromSubjectMaterial,
  useInstances,
  useLayers,
  useProjectConfig,
  useSetProjectRollUpStrategy,
  useSetLayerConfig,
} from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { describeStudyMaterialHint, formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { cn } from "@/ui/utils"
import { BaiduNetdiskImportDialog } from "@/views/settings/components/BaiduNetdiskImportDialog"

let nextTemplateItemId = 1

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
}

type SettingsPanelKey = "basic" | "ai" | "missing"
type LlmPromptAssemblyMode = "system" | "user_concat"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function createTemplateEditorItem(kind: "CONVERGENCE" | "REVIEW_TASK", count = 1): TemplateEditorItem {
  return {
    id: nextTemplateItemId++,
    kind,
    count: String(count),
  }
}

function toTemplateEditorItems(items: ReviewChainTemplateItem[]): TemplateEditorItem[] {
  return items.map((item) => createTemplateEditorItem(item.kind, item.count ?? 1))
}

function formatLastSeenAt(value: string | null | undefined) {
  if (!value) return "未记录"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function suggestTargetInstance(missingInstance: Instance, presentInstances: Instance[]) {
  return (
    presentInstances.find((item) => item.materialDisplayName === missingInstance.materialDisplayName)?.instanceId ??
    presentInstances[0]?.instanceId ??
    ""
  )
}

function describeDirectoryPermission(permission: "unsupported" | "missing" | "prompt" | "granted" | "denied") {
  if (permission === "unsupported") return "当前浏览器不支持目录授权"
  if (permission === "missing") return "未绑定目录"
  if (permission === "prompt") return "待授权"
  if (permission === "denied") return "已拒绝"
  return "已授权"
}

function describeDirectoryPermissionTone(permission: "unsupported" | "missing" | "prompt" | "granted" | "denied") {
  if (permission === "granted") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (permission === "prompt") return "border-amber-200 bg-amber-50 text-amber-700"
  if (permission === "denied") return "border-rose-200 bg-rose-50 text-rose-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function describeLlmSource(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "我的密钥"
  if (source === "global") return "全局密钥"
  if (source === "env") return "部署环境"
  return "未配置"
}

function describeLlmSourceTone(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (source === "global") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (source === "env") return "border-sky-200 bg-sky-50 text-sky-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function getRollUpStrategyLabel(strategy: RollUpStrategy) {
  if (strategy === "MANUAL") return "仅手动上推"
  if (strategy === "LEARNING_OBJECT_ISOMORPHIC") return "学习对象树同构上推"
  return "阈值自动上推"
}

function getRollUpStrategyDescription(strategy: RollUpStrategy) {
  if (strategy === "MANUAL") return "系统不会自动推进层级，只在你手动触发时推进。"
  if (strategy === "LEARNING_OBJECT_ISOMORPHIC") {
    return "只要某个学习对象节点下的实例都已有活跃复述点，系统就会把这个对象节点推进到对应层级。"
  }
  return "达到节点数或复述点阈值后，系统会自动进入聚合周期。"
}

function describeQuickStartTone(tone: "default" | "success" | "warning") {
  if (tone === "success") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (tone === "warning") return "border-amber-200 bg-amber-50 text-amber-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

type SettingsQuickStartStep = {
  key: string
  title: string
  description: string
  status: string
  tone: "default" | "success" | "warning"
  action?: {
    label: string
    onClick: () => void
    disabled?: boolean
    variant?: "outline"
  }
}

function SettingsQuickStartCard(props: {
  actionableMissingInstanceCount: number
  bookProjectAlreadyInitialized: boolean
  browserLocalMediaEnabled: boolean
  canChooseDirectory: boolean
  canRequestDirectoryPermission: boolean
  directoryBusy: boolean
  hasLearningContent: boolean
  learningContentLoading: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
  onAuthorizeDirectory: () => Promise<void>
  onGoWorkbench: () => void
  onImportAuthorizedDirectory: () => Promise<void>
  onOpenMissingPanel: () => void
  onRequestDirectoryPermission: () => Promise<void>
  onScrollToBookOutline: () => void
  onScrollToMistakeStructure: () => void
  projectType: ProjectType
  sourceCourseMaterialsCount: number
  sourceStructureMaterialsCount: number
}) {
  const {
    actionableMissingInstanceCount,
    bookProjectAlreadyInitialized,
    browserLocalMediaEnabled,
    canChooseDirectory,
    canRequestDirectoryPermission,
    directoryBusy,
    hasLearningContent,
    learningContentLoading,
    directoryPermission,
    onAuthorizeDirectory,
    onGoWorkbench,
    onImportAuthorizedDirectory,
    onOpenMissingPanel,
    onRequestDirectoryPermission,
    onScrollToBookOutline,
    onScrollToMistakeStructure,
    projectType,
    sourceCourseMaterialsCount,
    sourceStructureMaterialsCount,
  } = props

  const steps: SettingsQuickStartStep[] =
    projectType === "COURSE"
      ? [
          !browserLocalMediaEnabled
            ? {
                key: "course-directory-disabled",
                title: "先确认素材接入方式",
                description: "当前部署没有开启浏览器目录模式，这一步可以先跳过，直接回工作台录入或整理。",
                status: "当前未开启",
                tone: "default",
              }
            : directoryPermission === "granted" && learningContentLoading
              ? {
                  key: "course-directory-loading",
                  title: "正在确认内容目录",
                  description: "正在检查当前材料是否已经有可用内容。确认完成后，这里会给出更明确的下一步。",
                  status: "确认中",
                  tone: "default",
                }
            : directoryPermission === "granted" && hasLearningContent
              ? {
                  key: "course-directory-ready",
                  title: "内容目录已就绪",
                  description: "目录和内容都已准备好。回工作台选内容开始学习；本地文件有变化时再回来同步。",
                  status: "已就绪",
                  tone: "success",
                  action: {
                    label: "重新同步",
                    onClick: () => void onImportAuthorizedDirectory(),
                    disabled: directoryBusy,
                    variant: "outline",
                  },
                }
              : directoryPermission === "granted"
                ? {
                    key: "course-directory-import",
                    title: "先导入内容目录",
                    description: "目录已经接通。先把媒体文件扫进当前材料，再回工作台选内容开始学习。",
                    status: "待导入",
                    tone: "warning",
                    action: {
                      label: "导入内容",
                      onClick: () => void onImportAuthorizedDirectory(),
                      disabled: directoryBusy,
                    },
                  }
                : directoryPermission === "prompt" || directoryPermission === "denied"
                ? {
                    key: "course-directory-request",
                    title: "先恢复目录权限",
                    description: "浏览器已经记住这个目录，继续授权后就能重新扫描并导入里面的媒体文件。",
                    status: directoryPermission === "denied" ? "待重授权" : "待授权",
                    tone: "warning",
                    action: {
                      label: "继续授权",
                      onClick: () => void onRequestDirectoryPermission(),
                      disabled: !canRequestDirectoryPermission || directoryBusy,
                    },
                  }
                : directoryPermission === "missing"
                  ? {
                      key: "course-directory-choose",
                      title: "先绑定并授权素材目录",
                      description: "把视频所在目录接进当前材料，后面的导入、选内容和播放都会沿用这份绑定。",
                      status: "未绑定",
                      tone: "warning",
                      action: {
                        label: "选择目录",
                        onClick: () => void onAuthorizeDirectory(),
                        disabled: !canChooseDirectory || directoryBusy,
                      },
                    }
                  : {
                      key: "course-directory-unsupported",
                      title: "切到支持目录授权的浏览器",
                      description: "当前浏览器不支持目录授权。首轮使用建议切到桌面 Chrome 或 Edge，再回来绑定素材目录。",
                      status: "浏览器不支持",
                      tone: "warning",
                    },
          actionableMissingInstanceCount > 0
            ? {
                key: "course-missing-repair",
                title: "先修复缺失实例",
                description: `当前还有 ${actionableMissingInstanceCount} 个待修复的缺失实例，会影响同构上推和部分学习流。`,
                status: `${actionableMissingInstanceCount} 个待修复`,
                tone: "warning",
                action: {
                  label: "去修复",
                  onClick: onOpenMissingPanel,
                  variant: "outline",
                },
              }
            : {
                key: "course-missing-clear",
                title: "缺失实例已就绪",
                description: "当前没有挡住推进的缺失实例，可以继续往前走。",
                status: "已就绪",
                tone: "success",
              },
          {
            key: "course-go-workbench",
            title: "回工作台选内容开始学习",
            description: "目录和阻塞项处理好后，回工作台选中当前视频，再开始录入或复习。",
            status: "下一步",
            tone: "default",
            action: {
              label: "回工作台",
              onClick: onGoWorkbench,
              variant: "outline",
            },
          },
        ]
      : projectType === "BOOK"
        ? [
            bookProjectAlreadyInitialized
              ? {
                  key: "book-structure-ready",
                  title: "书本目录已就绪",
                  description: "当前书本材料已有目录节点和实例，可以直接回工作台选章节开始学习。",
                  status: "已就绪",
                  tone: "success",
                }
              : {
                  key: "book-structure-setup",
                  title: "先初始化书本目录",
                  description:
                    sourceCourseMaterialsCount > 0
                      ? "你可以一键复用同一学科下的网课树，也可以手动粘贴目录文本。先把这一步做完，后面录入和回看会顺很多。"
                      : "当前学科下还没有可复用的网课材料，直接在下方粘贴目录文本初始化，会是最快的起步方式。",
                  status: "待处理",
                  tone: "warning",
                  action: {
                    label: "去目录初始化",
                    onClick: onScrollToBookOutline,
                  },
                },
            {
              key: "book-go-workbench",
              title: "回工作台选章节开始学习",
              description: bookProjectAlreadyInitialized
                ? "目录已就绪。回工作台选中当前章节，再开始录入和回看。"
                : "初始化完目录后，回工作台选中当前章节，再开始录入和回看。",
              status: "下一步",
              tone: "default",
              action: {
                label: "回工作台",
                onClick: onGoWorkbench,
                variant: "outline",
              },
            },
          ]
        : projectType === "MISTAKE_BOOK"
          ? [
              bookProjectAlreadyInitialized
                ? {
                    key: "mistake-structure-ready",
                    title: "错题入口已就绪",
                    description: "当前错题材料已有目录节点或待整理入口，可以直接回工作台选条目开始整理。",
                    status: "已就绪",
                    tone: "success",
                  }
                : {
                    key: "mistake-structure-setup",
                    title: "先准备错题入口",
                    description:
                      sourceStructureMaterialsCount > 0
                        ? "你可以先创建一个“待整理”入口快速开用，也可以一键复用同学科的网课或书本结构。"
                        : "建议先创建一个“待整理”入口，先把错题收进来，后面再慢慢细分结构。",
                    status: "待处理",
                    tone: "warning",
                    action: {
                      label: "去初始化错题结构",
                      onClick: onScrollToMistakeStructure,
                    },
                  },
              {
                key: "mistake-go-workbench",
                title: "回工作台选条目开始整理",
                description: bookProjectAlreadyInitialized
                  ? "入口已就绪。回工作台选中当前条目，再开始录入和整理。"
                  : "入口准备好后，回工作台选中当前条目，再开始录入和整理。",
                status: "下一步",
                tone: "default",
                action: {
                  label: "回工作台",
                  onClick: onGoWorkbench,
                  variant: "outline",
                },
              },
            ]
          : [
              {
                key: "loose-points-go-workbench",
                title: "回工作台开始录入",
                description: "零散知识材料不需要目录授权或结构初始化，回工作台就能直接开始录入。",
                status: "下一步",
                tone: "success",
                action: {
                  label: "回工作台",
                  onClick: onGoWorkbench,
                },
              },
            ]

  const summary =
    projectType === "COURSE"
      ? "第一次使用先跑通“绑定并授权目录 -> 导入内容 -> 清掉阻塞项 -> 回工作台选内容开始学习”这条线，下面其他设置先不用一次看完。"
      : projectType === "BOOK"
        ? "先初始化书本目录，再回工作台选章节开始学习，会比先读完整页设置更省心。"
        : projectType === "MISTAKE_BOOK"
          ? "先准备错题入口，再回工作台选条目开始整理；这页里其他配置都可以后置。"
          : "零散知识模式没有额外门槛，回工作台就能直接开始录入。"

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>第一次使用，先按这个顺序</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-muted-foreground">{summary}</div>

        <div className="space-y-3">
          {steps.map((step, index) => (
            <div key={step.key} className="rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full border border-border/70 bg-background px-2 text-xs font-semibold text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="text-sm font-semibold text-foreground">{step.title}</span>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                        describeQuickStartTone(step.tone),
                      )}
                    >
                      {step.status}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">{step.description}</p>
                </div>

                {step.action ? (
                  <div className="flex justify-end lg:min-w-[9rem]">
                    <Button
                      type="button"
                      size="sm"
                      variant={step.action.variant}
                      onClick={step.action.onClick}
                      disabled={step.action.disabled}
                      className="w-full lg:w-auto"
                    >
                      {step.action.label}
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function PromptAssemblyModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: LlmPromptAssemblyMode
  onChange: (value: LlmPromptAssemblyMode) => void
  disabled: boolean
}) {
  const options: Array<{
    value: LlmPromptAssemblyMode
    title: string
    description: string
  }> = [
    {
      value: "system",
      title: "系统信息",
      description: "优先让兼容 OpenAI 的主流 chat 模型按 system/context 角色理解规则与上下文。",
    },
    {
      value: "user_concat",
      title: "拼接到用户信息",
      description: "把系统规则和节点上下文一并拼进用户消息，适合 qvq 这类对 system 遵循较弱的模型。",
    },
  ]

  return (
    <div className="grid gap-2 md:grid-cols-2">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-[1rem] border px-4 py-3 text-left transition",
              active
                ? "border-sky-400 bg-sky-50/80 shadow-[0_10px_30px_rgba(14,116,144,0.12)]"
                : "border-border/70 bg-background hover:border-sky-200 hover:bg-sky-50/40",
              disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-foreground">{option.title}</span>
              <span
                className={cn(
                  "inline-flex h-5 min-w-5 items-center justify-center rounded-full border px-1.5 text-[11px] font-semibold",
                  active ? "border-sky-400 bg-sky-500 text-white" : "border-border/60 text-muted-foreground",
                )}
              >
                {active ? "当前" : "可选"}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{option.description}</p>
          </button>
        )
      })}
    </div>
  )
}

function isDirectoryPickerAbort(err: unknown) {
  return err instanceof DOMException && err.name === "AbortError"
}

function countOutlineIndentDepth(rawLine: string) {
  const prefix = rawLine.match(/^[\t ]*/)?.[0] ?? ""
  let visualColumns = 0
  for (const ch of prefix) {
    visualColumns += ch === "\t" ? 2 : 1
  }
  return Math.floor(visualColumns / 2)
}

function parseBookOutlineDraft(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => ({ rawLine: line, title: line.trim() }))
    .filter((line) => line.title.length > 0)
    .map((line) => ({
      depth: countOutlineIndentDepth(line.rawLine),
      title: line.title,
    }))
}

function SettingsPanelSwitchCard(props: {
  title: string
  status: string
  icon: typeof Settings2
  active: boolean
  tone?: "default" | "success" | "warning"
  onClick: () => void
}) {
  const { title, status, icon: Icon, active, tone = "default", onClick } = props
  const toneClass =
    tone === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-600"

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group rounded-[1.55rem] border px-4 py-4 text-left transition-all",
        active
          ? "border-primary/30 bg-[linear-gradient(180deg,hsl(var(--primary)/0.11),hsl(var(--background)))] shadow-[0_26px_60px_-40px_hsl(var(--primary)/0.45)]"
          : "border-border/70 bg-card hover:border-primary/18 hover:bg-[hsl(var(--primary)/0.05)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[color:var(--theme-soft-bg)] text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold", toneClass)}>{status}</span>
      </div>
      <div className="mt-4 text-base font-semibold tracking-tight text-foreground">{title}</div>
    </button>
  )
}

export function ProjectSettingsPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const projectQ = useProject(pid, { enabled: !!pid })
  const subjectContextQ = useSubjectContext(pid, !!pid)
  const createSubjectMaterialM = useCreateSubjectMaterial()
  const editSubjectM = useEditSubject()
  const deleteSubjectM = useDeleteSubject()
  const editSubjectMaterialM = useEditSubjectMaterial()
  const deleteSubjectMaterialM = useDeleteSubjectMaterial()
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const globalLlmSettingsQ = useGlobalLlmSettings(capabilitiesQ.data !== undefined && !authEnabled)
  const updateGlobalLlmSettingsM = useUpdateGlobalLlmSettings()
  const myLlmSettingsQ = useMyLlmSettings(authEnabled)
  const updateMyLlmSettingsM = useUpdateMyLlmSettings()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const directoryPermission = directoryBinding.permission
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const baiduNetdiskEnabled = capabilitiesQ.data?.baiduNetdiskEnabled ?? false

  const layersQ = useLayers(pid)
  const projectConfigQ = useProjectConfig(pid)
  const instancesQ = useInstances(pid)
  const importLearningObjectsM = useImportLearningObjectsFromBrowser(pid)
  const initializeBookLearningObjectsM = useInitializeBookLearningObjects(pid)
  const initializeBookFromMaterialM = useInitializeBookLearningObjectsFromSubjectMaterial(pid)
  const ensureMistakeInboxM = useEnsureMistakeInbox(pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const setProjectRollUpStrategyM = useSetProjectRollUpStrategy(pid)
  const bulkRemapM = useBulkRemapRecallPointsInstance(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const currentRollUpStrategy = projectConfigQ.data?.rollUpStrategy ?? "THRESHOLD_AUTO"
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const removeRecentProjectId = useAppStore((state) => state.removeRecentProjectId)
  const subjectContext = subjectContextQ.data
  const subjectProjectId = subjectContext?.subjectProjectId ?? pid
  const isSubjectRoot = subjectContext?.isSubjectRoot ?? true
  const subjectTitle = subjectContext?.subject.title ?? projectQ.project?.title ?? ""
  const currentMaterial = subjectContext?.currentMaterial ?? null
  const currentMaterialTitle = currentMaterial?.title ?? projectQ.project?.title ?? ""
  const currentMaterialType =
    currentMaterial?.materialType ??
    (projectType === "BOOK"
      ? "BOOK"
      : projectType === "MISTAKE_BOOK"
        ? "MISTAKE_BOOK"
        : projectType === "LOOSE_POINTS"
          ? "LOOSE_POINTS"
          : "COURSE")
  const subjectMaterials = subjectContext?.materials ?? []
  const sourceCourseMaterials = subjectMaterials.filter(
    (material) => material.materialType === "COURSE" && material.compatibilityProjectId && material.compatibilityProjectId !== pid,
  )
  const sourceStructureMaterials = subjectMaterials.filter(
    (material) =>
      (material.materialType === "COURSE" || material.materialType === "BOOK") &&
      material.compatibilityProjectId &&
      material.compatibilityProjectId !== pid,
  )
  const canDeleteCurrentMaterial =
    !isSubjectRoot &&
    currentMaterial !== null &&
    currentMaterial.compatibilityProjectId !== null &&
    currentMaterial.compatibilityProjectId !== subjectProjectId

  const existingLayerIndexes = useMemo(() => (layersQ.data ?? []).map((l) => l.layerIndex).sort((a, b) => a - b), [layersQ.data])
  const defaultLayerConfig = useMemo(
    () => ({ reviewChainTemplate: [{ kind: "CONVERGENCE" as const }], aggregationKNode: 10, aggregationKPoint: 200, thresholdRollUpEnabled: true }),
    [],
  )

  const [configLayerIndex, setConfigLayerIndex] = useState(0)
  const effectiveConfigLayerIndex = configLayerIndex
  const knownLayerIndexes = useMemo(() => [0, 1, 2, 3, 4, 5], [])
  const selectedLayerExists = existingLayerIndexes.includes(effectiveConfigLayerIndex)
  const selectedLayerHasSavedConfig =
    projectConfigQ.data?.layerConfigs[String(effectiveConfigLayerIndex)] !== undefined

  const effectiveLayerConfig = useMemo(() => {
    const k = String(effectiveConfigLayerIndex)
    return projectConfigQ.data?.layerConfigs[k] ?? defaultLayerConfig
  }, [defaultLayerConfig, effectiveConfigLayerIndex, projectConfigQ.data?.layerConfigs])
  const templateConfigSignature = useMemo(
    () => JSON.stringify(effectiveLayerConfig.reviewChainTemplate),
    [effectiveLayerConfig.reviewChainTemplate],
  )
  const layerConfigVersion = `${currentRollUpStrategy}:${effectiveConfigLayerIndex}:${effectiveLayerConfig.aggregationKNode}:${effectiveLayerConfig.aggregationKPoint}:${effectiveLayerConfig.thresholdRollUpEnabled}:${templateConfigSignature}`

  const [remapTargets, setRemapTargets] = useState<Record<string, string>>({})
  const [directoryAction, setDirectoryAction] = useState<"authorize" | "request" | "clear" | "import" | null>(null)
  const [bookOutlineDraft, setBookOutlineDraft] = useState("")
  const [isBaiduImportDialogOpen, setIsBaiduImportDialogOpen] = useState(false)

  const missingInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence === "MISSING"),
    [instancesQ.data],
  )
  const presentInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence !== "MISSING"),
    [instancesQ.data],
  )

  const missingRecallPointQs = useQueries({
    queries: missingInstances.map((instance) => ({
      queryKey: ["recallPointsByInstance", pid, instance.instanceId],
      queryFn: () => listRecallPointsByInstance(pid, instance.instanceId),
      enabled: !!pid,
    })),
  })

  const recallPointIdsByInstanceId = useMemo(() => {
    const out: Record<string, string[]> = {}
    missingInstances.forEach((instance, index) => {
      out[instance.instanceId] = missingRecallPointQs[index]?.data?.recallPointIds ?? []
    })
    return out
  }, [missingInstances, missingRecallPointQs])
  const actionableMissingInstances = useMemo(
    () =>
      missingInstances.filter((_, index) => {
        const query = missingRecallPointQs[index]
        if (!query || query.isLoading || query.error) return true
        return (query.data?.recallPointIds ?? []).length > 0
      }),
    [missingInstances, missingRecallPointQs],
  )
  const missingRepairCountsLoading = missingInstances.length > 0 && missingRecallPointQs.some((query) => query.isLoading)

  const canChooseDirectory = !!pid && !directoryBinding.loading && directoryBinding.supported
  const canRequestDirectoryPermission =
    !!pid && !directoryBinding.loading && (directoryPermission === "prompt" || directoryPermission === "denied")
  const canClearDirectory = !!pid && !directoryBinding.loading && directoryPermission !== "missing"
  const directoryBusy = directoryAction !== null
  const [activePanel, setActivePanel] = useState<SettingsPanelKey>("basic")
  const supportsMissingInstanceRepair = projectType !== "LOOSE_POINTS" && projectType !== "MISTAKE_BOOK"

  const directoryStatusText =
    projectType === "BOOK"
      ? "目录初始化"
      : projectType === "MISTAKE_BOOK"
        ? "错题结构"
      : projectType === "LOOSE_POINTS"
        ? "零散模式"
        : browserLocalMediaEnabled
          ? directoryPermission === "granted"
            ? "目录已接通"
            : directoryPermission === "denied"
              ? "等待重授权"
              : directoryPermission === "prompt"
                ? "等待授权"
                : "待配置"
          : "基础配置"
  const aiStatusText = capabilitiesQ.data?.llmConfigured ? "LLM 已可用" : "LLM 未接通"
  const missingStatusText =
    projectType === "LOOSE_POINTS" || projectType === "MISTAKE_BOOK"
      ? "不适用"
      : missingRepairCountsLoading
        ? "整理中..."
        : actionableMissingInstances.length > 0
          ? `${actionableMissingInstances.length} 个待修复`
          : "当前无缺失实例"
  const parsedBookOutlineItems = useMemo(() => parseBookOutlineDraft(bookOutlineDraft), [bookOutlineDraft])
  const bookOutlineValidationMessage = useMemo(() => {
    if (projectType !== "BOOK" && projectType !== "MISTAKE_BOOK") return null
    if (parsedBookOutlineItems.length === 0) return "请先粘贴目录文本。"
    if (parsedBookOutlineItems[0]?.depth !== 0) return "目录第一行必须是顶层节点，不能带缩进。"
    for (let index = 1; index < parsedBookOutlineItems.length; index += 1) {
      if (parsedBookOutlineItems[index].depth - parsedBookOutlineItems[index - 1].depth > 1) {
        return "目录层级每次最多只能向下增加一级缩进。"
      }
    }
    return null
  }, [parsedBookOutlineItems, projectType])
  const bookProjectAlreadyInitialized = (instancesQ.data?.length ?? 0) > 0

  useEffect(() => {
    if (!supportsMissingInstanceRepair && activePanel === "missing") {
      setActivePanel("basic")
    }
  }, [activePanel, supportsMissingInstanceRepair])

  function scrollToSettingsSection(sectionId: string) {
    const section = document.getElementById(sectionId)
    if (!section) return
    section.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  function clearProjectLocalState(projectIds: string[]) {
    const uniqueProjectIds = Array.from(new Set(projectIds.filter(Boolean)))
    for (const projectId of uniqueProjectIds) {
      useWorkbenchStore.getState().resetProject(projectId)
      removeRecentProjectId(projectId)
    }
  }

  async function onRemapMissingInstance(fromInstanceId: string) {
    const sourceInstance = actionableMissingInstances.find((item) => item.instanceId === fromInstanceId) ?? missingInstances.find((item) => item.instanceId === fromInstanceId)
    const toInstanceId = remapTargets[fromInstanceId] ?? (sourceInstance ? suggestTargetInstance(sourceInstance, presentInstances) : "")
    if (!toInstanceId) return
    const targetInstance = presentInstances.find((item) => item.instanceId === toInstanceId)
    try {
      await bulkRemapM.mutateAsync({ fromInstanceId, toInstanceId })
      showSuccessFeedback(
        "复述点已迁移",
        `已把 ${sourceInstance?.materialDisplayName ?? "缺失实例"} 的锚点迁移到 ${targetInstance?.materialDisplayName ?? "目标实例"}。`,
      )
    } catch (err) {
      showErrorFeedback("迁移复述点失败", formatApiError(err))
    }
  }

  async function onAuthorizeDirectory() {
    if (!canChooseDirectory || directoryBusy) return
    setDirectoryAction("authorize")
    try {
      const permission = await directoryBinding.authorizeDirectory()
      if (permission === "granted") {
        showSuccessFeedback("本地目录已绑定", `浏览器已经记录并授权${isSubjectRoot ? "当前默认网课材料" : "当前材料"}的本地素材目录。`)
        await importAuthorizedDirectory(true)
        return
      } else {
        showInfoFeedback("目录已记录", `目录已经保存到${isSubjectRoot ? "当前默认网课材料" : "当前材料"}，但浏览器还需要你继续授予读取权限。`)
      }
    } catch (err) {
      if (!isDirectoryPickerAbort(err)) {
        showErrorFeedback("绑定本地目录失败", formatApiError(err))
      }
    } finally {
      setDirectoryAction((current) => (current === "authorize" ? null : current))
    }
  }

  async function onRequestDirectoryPermission() {
    if (!canRequestDirectoryPermission || directoryBusy) return
    setDirectoryAction("request")
    try {
      const permission = await directoryBinding.requestPermission()
      if (permission === "granted") {
        showSuccessFeedback("目录权限已恢复", `现在可以扫描并导入${isSubjectRoot ? "默认网课材料" : "当前材料"}的本地素材目录。`)
        await importAuthorizedDirectory(true)
        return
      } else if (permission === "denied") {
        showInfoFeedback("目录权限未授予", "浏览器仍未允许读取该目录，你可以重试或直接更换目录。")
      } else {
        showInfoFeedback("等待目录授权", "浏览器还没有授予读取权限，请继续完成授权。")
      }
    } catch (err) {
      showErrorFeedback("请求目录权限失败", formatApiError(err))
    } finally {
      setDirectoryAction((current) => (current === "request" ? null : current))
    }
  }

  async function importAuthorizedDirectory(silentSuccess = false) {
    if (!pid) return
    setDirectoryAction("import")
    try {
      const scan = await scanProjectDirectoryMedia(pid)
      const result = await importLearningObjectsM.mutateAsync(scan)
      if (result.unchanged) {
        if (!silentSuccess) {
          showInfoFeedback("目录已是最新", "当前已授权目录里的媒体文件没有变化。")
        }
        return
      }
      showSuccessFeedback(
        "内容目录已导入",
        `已导入 ${scan.relativeFilePaths.length} 个媒体文件，新增 ${result.created_instances_count} 个实例。`,
      )
    } catch (err) {
      showErrorFeedback("导入本地目录失败", formatApiError(err))
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onImportAuthorizedDirectory(silentSuccess = false) {
    if (!pid || directoryBusy) return
    await importAuthorizedDirectory(silentSuccess)
  }

  async function onClearDirectoryBinding() {
    if (!canClearDirectory || directoryBusy) return
    setDirectoryAction("clear")
    try {
      await directoryBinding.clearDirectory()
      showSuccessFeedback("本地目录绑定已清除", `${isSubjectRoot ? "当前默认网课材料" : "当前材料"}不再保留这个浏览器里的目录授权记录。`)
    } catch (err) {
      showErrorFeedback("清除本地目录绑定失败", formatApiError(err))
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onInitializeBookOutline() {
    if (projectType !== "BOOK" && projectType !== "MISTAKE_BOOK") return
    if (bookOutlineValidationMessage) {
      showInfoFeedback("目录暂时还不能初始化", bookOutlineValidationMessage)
      return
    }
    try {
      const result = await initializeBookLearningObjectsM.mutateAsync({ items: parsedBookOutlineItems })
      showSuccessFeedback(
        projectType === "MISTAKE_BOOK" ? "错题结构已初始化" : "书本目录已初始化",
        projectType === "MISTAKE_BOOK"
          ? `已创建 ${result.created_learning_object_nodes_count} 个错题目录节点和 ${result.created_instances_count} 个归档条目。`
          : `已创建 ${result.created_learning_object_nodes_count} 个目录节点和 ${result.created_instances_count} 个书本实例。`,
      )
    } catch (err) {
      showErrorFeedback(projectType === "MISTAKE_BOOK" ? "初始化错题结构失败" : "初始化书本目录失败", formatApiError(err))
    }
  }

  async function onInitializeBookFromMaterial(sourceMaterialId: string) {
    if (projectType !== "BOOK" && projectType !== "MISTAKE_BOOK") return
    if (!sourceMaterialId.trim()) {
      showInfoFeedback("还没选来源材料", "先选一个要复用的来源材料，再开始初始化。")
      return
    }
    try {
      const result = await initializeBookFromMaterialM.mutateAsync({ sourceMaterialId })
      showSuccessFeedback(
        projectType === "MISTAKE_BOOK" ? "错题结构已复用来源树" : "书本目录已复用网课树",
        projectType === "MISTAKE_BOOK"
          ? `已创建 ${result.created_learning_object_nodes_count} 个错题目录节点和 ${result.created_instances_count} 个归档条目。`
          : `已创建 ${result.created_learning_object_nodes_count} 个目录节点和 ${result.created_instances_count} 个书本实例。`,
      )
    } catch (err) {
      showErrorFeedback(projectType === "MISTAKE_BOOK" ? "复用来源树失败" : "复用网课树失败", formatApiError(err))
    }
  }

  async function onEnsureMistakeInbox() {
    if (projectType !== "MISTAKE_BOOK") return
    try {
      const result = await ensureMistakeInboxM.mutateAsync()
      showSuccessFeedback(
        result.created ? "待整理入口已创建" : "待整理入口已就绪",
        "现在可以直接把错题收进这个材料，或者手动开始录入整理。",
      )
    } catch (err) {
      showErrorFeedback("创建待整理入口失败", formatApiError(err))
    }
  }

  const renameMutationError = isSubjectRoot ? editSubjectM.error : editSubjectMaterialM.error
  const renameMutationPending = isSubjectRoot ? editSubjectM.isPending : editSubjectMaterialM.isPending
  const deleteMutationError = isSubjectRoot ? deleteSubjectM.error : deleteSubjectMaterialM.error
  const deleteMutationPending = isSubjectRoot ? deleteSubjectM.isPending : deleteSubjectMaterialM.isPending

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少学科上下文"
          message="当前链接缺少学科信息。请先返回学科列表，再重新进入学科设置。"
          action={<Button onClick={() => navigate("/projects")}>返回学科列表</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <Card className="theme-card">
        <CardHeader className="pb-4">
          <CardTitle>设置分区</CardTitle>
        </CardHeader>
        <CardContent className={cn("grid gap-3", supportsMissingInstanceRepair ? "md:grid-cols-3" : "md:grid-cols-2")}>
          <SettingsPanelSwitchCard
            title="基本设置"
            status={directoryStatusText}
            icon={Settings2}
            active={activePanel === "basic"}
            tone={directoryPermission === "granted" ? "success" : "default"}
            onClick={() => setActivePanel("basic")}
          />
          <SettingsPanelSwitchCard
            title="AI 设置"
            status={aiStatusText}
            icon={Sparkles}
            active={activePanel === "ai"}
            tone={capabilitiesQ.data?.llmConfigured ? "success" : "default"}
            onClick={() => setActivePanel("ai")}
          />
          {supportsMissingInstanceRepair ? (
            <SettingsPanelSwitchCard
              title="缺失实例设置"
              status={missingStatusText}
              icon={TriangleAlert}
              active={activePanel === "missing"}
              tone={missingRepairCountsLoading || actionableMissingInstances.length > 0 ? "warning" : "default"}
              onClick={() => setActivePanel("missing")}
            />
          ) : null}
        </CardContent>
      </Card>

      {activePanel === "basic" ? (
        <>
          <SettingsQuickStartCard
            actionableMissingInstanceCount={actionableMissingInstances.length}
            bookProjectAlreadyInitialized={bookProjectAlreadyInitialized}
            browserLocalMediaEnabled={browserLocalMediaEnabled}
            canChooseDirectory={canChooseDirectory}
            canRequestDirectoryPermission={canRequestDirectoryPermission}
            directoryBusy={directoryBusy}
            hasLearningContent={(instancesQ.data?.length ?? 0) > 0}
            learningContentLoading={instancesQ.isLoading}
            directoryPermission={directoryPermission}
            onAuthorizeDirectory={onAuthorizeDirectory}
            onGoWorkbench={() => {
              navigate(`/p/${pid}/workbench`)
            }}
            onImportAuthorizedDirectory={() => onImportAuthorizedDirectory()}
            onOpenMissingPanel={() => setActivePanel("missing")}
            onRequestDirectoryPermission={onRequestDirectoryPermission}
            onScrollToBookOutline={() => scrollToSettingsSection("settings-book-outline")}
            onScrollToMistakeStructure={() => scrollToSettingsSection("settings-mistake-structure")}
            projectType={projectType}
            sourceCourseMaterialsCount={sourceCourseMaterials.length}
            sourceStructureMaterialsCount={sourceStructureMaterials.length}
          />

          <SettingsScopeCard
            isSubjectRoot={isSubjectRoot}
            materialTitle={currentMaterialTitle}
            materialType={currentMaterialType}
            onOpenSubjectSettings={
              !isSubjectRoot && subjectProjectId
                ? () => {
                    navigate(`/p/${subjectProjectId}/settings`)
                  }
                : undefined
            }
            subjectTitle={subjectTitle}
          />

          <SubjectMaterialsCard
            createError={createSubjectMaterialM.error}
            currentProjectId={pid}
            createPending={createSubjectMaterialM.isPending}
            error={subjectContextQ.error}
            isLoading={subjectContextQ.isLoading}
            isSubjectRoot={isSubjectRoot}
            materials={subjectMaterials}
            onCreateMaterial={async (materialType, title) => {
              try {
                const created = await createSubjectMaterialM.mutateAsync({ subjectId: subjectProjectId, materialType, title })
                showSuccessFeedback("学习材料已创建", `“${created.title}” 已挂到“${subjectTitle || "当前学科"}”下。`)
                if (created.compatibilityProjectId) {
                  navigate(created.materialType === "BOOK" ? `/p/${created.compatibilityProjectId}/settings` : `/p/${created.compatibilityProjectId}/workbench`)
                }
              } catch (err) {
                showErrorFeedback("创建学习材料失败", formatApiError(err))
                throw err
              }
            }}
            onOpenMaterial={(material, target) => {
              if (!material.compatibilityProjectId) return
              navigate(target === "settings" ? `/p/${material.compatibilityProjectId}/settings` : `/p/${material.compatibilityProjectId}/workbench`)
            }}
            subjectTitle={subjectTitle}
          />

          <BasicInfoCard
            actionableMissingInstanceCount={actionableMissingInstances.length}
            baiduNetdiskEnabled={baiduNetdiskEnabled}
            browserLocalMediaEnabled={browserLocalMediaEnabled}
            canChooseDirectory={canChooseDirectory}
            canClearDirectory={canClearDirectory}
            canRequestDirectoryPermission={canRequestDirectoryPermission}
            directoryAction={directoryAction}
            directoryBinding={directoryBinding}
            directoryBusy={directoryBusy}
            directoryPermission={directoryPermission}
            entityLabel={isSubjectRoot ? "学科" : "材料"}
            entityPlaceholder={isSubjectRoot ? "输入新的学科名称" : "输入新的材料名称"}
            entitySaveLabel={isSubjectRoot ? "保存学科名称" : "保存材料名称"}
            entityTitle={isSubjectRoot ? subjectTitle : currentMaterialTitle}
            importError={importLearningObjectsM.error}
            isLoading={projectQ.isLoading || subjectContextQ.isLoading}
            isPending={renameMutationPending}
            isSubjectRoot={isSubjectRoot}
            materialTitle={currentMaterialTitle}
            materialType={currentMaterialType}
            onOpenSubjectSettings={
              !isSubjectRoot && subjectProjectId
                ? () => {
                    navigate(`/p/${subjectProjectId}/settings`)
                  }
                : undefined
            }
            projectType={projectType}
            queryError={subjectContextQ.error ?? projectQ.error}
            rollUpStrategy={currentRollUpStrategy}
            saveError={renameMutationError}
            rollUpStrategyError={setProjectRollUpStrategyM.error}
            rollUpStrategySaving={setProjectRollUpStrategyM.isPending}
            subjectTitle={subjectTitle}
            onAuthorizeDirectory={onAuthorizeDirectory}
            onChangeRollUpStrategy={async (nextStrategy) => {
              try {
                await setProjectRollUpStrategyM.mutateAsync(nextStrategy)
                showSuccessFeedback("上推策略已更新", `当前材料已切换到“${getRollUpStrategyLabel(nextStrategy)}”。`)
              } catch (err) {
                showErrorFeedback("更新上推策略失败", formatApiError(err))
              }
            }}
            onClearDirectoryBinding={onClearDirectoryBinding}
            onOpenBaiduImport={() => setIsBaiduImportDialogOpen(true)}
            onImportAuthorizedDirectory={onImportAuthorizedDirectory}
            onRequestDirectoryPermission={onRequestDirectoryPermission}
            onSave={async (title) => {
              try {
                if (isSubjectRoot) {
                  await editSubjectM.mutateAsync({ subjectId: subjectProjectId, title })
                  showSuccessFeedback("学科名称已更新", `当前学科现在显示为“${title}”。`)
                  return
                }
                if (!currentMaterial) {
                  showInfoFeedback("材料信息仍在加载", "等材料上下文同步完成后再试一次。")
                  return
                }
                await editSubjectMaterialM.mutateAsync({ subjectId: subjectProjectId, materialId: currentMaterial.materialId, title })
                showSuccessFeedback("材料名称已更新", `当前材料现在显示为“${title}”。`)
              } catch (err) {
                showErrorFeedback(isSubjectRoot ? "更新学科名称失败" : "更新材料名称失败", formatApiError(err))
              }
            }}
            layerConfigSection={
              <LayerConfigEditor
                key={layerConfigVersion}
                embedded
                canSave={!!pid}
                existingLayerIndexes={existingLayerIndexes}
                initialConfig={effectiveLayerConfig}
                knownLayerIndexes={knownLayerIndexes}
                layersError={layersQ.error}
                mutationError={setLayerConfigM.error}
                projectConfigError={projectConfigQ.error}
                rollUpStrategy={currentRollUpStrategy}
                selectedLayerExists={selectedLayerExists}
                selectedLayerHasSavedConfig={selectedLayerHasSavedConfig}
                selectedLayerIndex={effectiveConfigLayerIndex}
                saving={setLayerConfigM.isPending}
                onSave={async ({ kNode, kPoint, reviewChainTemplate, thresholdRollUpEnabled }) => {
                  try {
                    await setLayerConfigM.mutateAsync({
                      layerIndex: effectiveConfigLayerIndex,
                      kNode,
                      kPoint,
                      reviewChainTemplate,
                      thresholdRollUpEnabled,
                    })
                    showSuccessFeedback(
                      selectedLayerExists ? "层配置已保存" : "未来层预配置已保存",
                      selectedLayerExists
                        ? currentRollUpStrategy === "THRESHOLD_AUTO"
                          ? `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤，节点阈值 ${kNode}，复述点阈值 ${kPoint}，阈值自动上推已${thresholdRollUpEnabled ? "开启" : "关闭"}。`
                          : `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤；阈值参数也已保存，等切回“阈值自动上推”时会继续沿用。`
                        : currentRollUpStrategy === "THRESHOLD_AUTO"
                          ? `第 ${effectiveConfigLayerIndex} 层还不存在，已先保存预配置；等它被创建时会自动使用这 ${reviewChainTemplate.length} 个模板步骤、当前阈值和阈值自动上推${thresholdRollUpEnabled ? "开启" : "关闭"}状态。`
                          : `第 ${effectiveConfigLayerIndex} 层还不存在，已先保存预配置；等它被创建时会自动使用这 ${reviewChainTemplate.length} 个模板步骤，并保留当前阈值参数。`,
                    )
                  } catch (err) {
                    showErrorFeedback("保存层配置失败", formatApiError(err))
                  }
                }}
                onSelectedLayerIndexChange={setConfigLayerIndex}
              />
            }
          />

          {projectType === "BOOK" ? (
            <div id="settings-book-outline">
              <BookOutlineSetupCard
                courseMaterials={sourceCourseMaterials}
                draftValue={bookOutlineDraft}
                initialized={bookProjectAlreadyInitialized}
                initializeFromMaterialError={initializeBookFromMaterialM.error}
                initializeFromMaterialPending={initializeBookFromMaterialM.isPending}
                isPending={initializeBookLearningObjectsM.isPending}
                mutationError={initializeBookLearningObjectsM.error}
                onChange={setBookOutlineDraft}
                onInitializeFromMaterial={onInitializeBookFromMaterial}
                onInitialize={onInitializeBookOutline}
                parsedCount={parsedBookOutlineItems.length}
                validationMessage={bookOutlineValidationMessage}
              />
            </div>
          ) : null}

          {projectType === "MISTAKE_BOOK" ? (
            <div id="settings-mistake-structure">
              <MistakeStructureSetupCard
                sourceMaterials={sourceStructureMaterials}
                initialized={bookProjectAlreadyInitialized}
                initializeFromMaterialError={initializeBookFromMaterialM.error}
                initializeFromMaterialPending={initializeBookFromMaterialM.isPending}
                ensureInboxError={ensureMistakeInboxM.error}
                ensureInboxPending={ensureMistakeInboxM.isPending}
                isPending={initializeBookLearningObjectsM.isPending}
                mutationError={initializeBookLearningObjectsM.error}
                draftValue={bookOutlineDraft}
                onChange={setBookOutlineDraft}
                onEnsureInbox={onEnsureMistakeInbox}
                onInitializeFromMaterial={onInitializeBookFromMaterial}
                onInitialize={onInitializeBookOutline}
                parsedCount={parsedBookOutlineItems.length}
                validationMessage={bookOutlineValidationMessage}
              />
            </div>
          ) : null}

          {isSubjectRoot || canDeleteCurrentMaterial ? (
            <DangerZoneCard
              actionLabel={isSubjectRoot ? "删除学科" : "删除当前材料"}
              actionPendingLabel={isSubjectRoot ? "删除学科中..." : "删除材料中..."}
              confirmationLabel={isSubjectRoot ? "输入学科标题以确认删除" : "输入材料名称以确认删除"}
              deleteError={deleteMutationError}
              description={
                isSubjectRoot
                  ? `删除学科会一起移除当前学科和下面的 ${Math.max(0, subjectMaterials.length - 1)} 份附属材料兼容入口，本地工作台缓存也会一并清理。`
                  : `删除材料只会移除“${currentMaterialTitle || "当前材料"}”和它的兼容工作台，学科“${subjectTitle || "当前学科"}”以及其他材料会保留。`
              }
              isPending={deleteMutationPending}
              onDelete={async () => {
                try {
                  if (isSubjectRoot) {
                    const relatedProjectIds = [subjectProjectId, ...subjectMaterials.map((material) => material.compatibilityProjectId ?? "")]
                    await deleteSubjectM.mutateAsync(subjectProjectId)
                    clearProjectLocalState(relatedProjectIds)
                    setSelectedProjectId("")
                    showSuccessFeedback("学科已删除", `“${subjectTitle || "当前学科"}”和它下面的材料入口都已移除。`)
                    navigate("/projects")
                    return
                  }
                  if (!currentMaterial) {
                    showInfoFeedback("材料信息仍在加载", "等材料上下文同步完成后再试一次。")
                    return
                  }
                  await deleteSubjectMaterialM.mutateAsync({ subjectId: subjectProjectId, materialId: currentMaterial.materialId })
                  clearProjectLocalState([pid])
                  setSelectedProjectId(subjectProjectId)
                  showSuccessFeedback("材料已删除", `“${currentMaterial.title}” 已从“${subjectTitle || "当前学科"}”下移除。`)
                  navigate(`/p/${subjectProjectId}/settings`)
                } catch (err) {
                  showErrorFeedback(isSubjectRoot ? "删除学科失败" : "删除材料失败", formatApiError(err))
                }
              }}
              targetTitle={isSubjectRoot ? subjectTitle : currentMaterialTitle}
            />
          ) : null}

          <BaiduNetdiskImportDialog
            projectId={pid}
            open={isBaiduImportDialogOpen}
            onOpenChange={setIsBaiduImportDialogOpen}
          />
        </>
      ) : null}

      {activePanel === "ai" ? (
        <div className="space-y-5">
          {authEnabled ? (
            <>
              <UserLlmSettingsCard
                queryError={myLlmSettingsQ.error}
                saveError={updateMyLlmSettingsM.error}
                settings={myLlmSettingsQ.data}
                isLoading={myLlmSettingsQ.isLoading}
                isPending={updateMyLlmSettingsM.isPending}
                onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
                  try {
                    await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
                    showSuccessFeedback("我的 LLM 密钥已清除", "当前账号会停止使用已保存密钥；未重新保存前，这个账号的 LLM 能力视为未接通。")
                  } catch (err) {
                    showErrorFeedback("清除我的 LLM 密钥失败", formatApiError(err))
                  }
                }}
                onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
                  try {
                    await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
                    showSuccessFeedback("我的 LLM 设置已保存", "当前账号之后在任意设备登录时都会复用这份 LLM 服务配置。")
                  } catch (err) {
                    showErrorFeedback("保存我的 LLM 设置失败", formatApiError(err))
                  }
                }}
              />
            </>
          ) : (
            <>
              <GlobalLlmSettingsCard
                title="全局 LLM 设置"
                saveLabel="保存全局设置"
                queryError={globalLlmSettingsQ.error}
                saveError={updateGlobalLlmSettingsM.error}
                settings={globalLlmSettingsQ.data}
                isLoading={globalLlmSettingsQ.isLoading}
                isPending={updateGlobalLlmSettingsM.isPending}
                onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
                  try {
                    await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
                    showSuccessFeedback("全局 LLM 密钥已清除", "系统会停止使用已保存的全局密钥。")
                  } catch (err) {
                    showErrorFeedback("清除全局 LLM 密钥失败", formatApiError(err))
                  }
                }}
                onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
                  try {
                    await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
                    showSuccessFeedback("全局 LLM 设置已保存", "后端现在会通过已配置服务代理后续的大模型能力请求。")
                  } catch (err) {
                    showErrorFeedback("保存全局 LLM 设置失败", formatApiError(err))
                  }
                }}
              />
            </>
          )}
        </div>
      ) : null}

      {supportsMissingInstanceRepair && activePanel === "missing" ? (
      <Card className="theme-card">
        <CardHeader>
          <CardTitle>缺失材料修复</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {instancesQ.isLoading ? <p className="text-sm text-muted-foreground">加载实例中...</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length > 0 ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
              这里只显示仍有活跃复述点需要迁移的缺失实例；已经没有迁移价值的旧实例会自动从列表里消失。
            </div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && missingRepairCountsLoading ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">正在整理仍需迁移的缺失实例...</div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length === 0 ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">当前没有需要迁移的缺失材料实例。</div>
          ) : null}

          <div className="space-y-3">
            {actionableMissingInstances.map((instance) => {
              const index = missingInstances.findIndex((item) => item.instanceId === instance.instanceId)
              const recallPointIds = recallPointIdsByInstanceId[instance.instanceId] ?? []
              const countQuery = missingRecallPointQs[index]
              const targetInstanceId = remapTargets[instance.instanceId] ?? suggestTargetInstance(instance, presentInstances)

              return (
                <div key={instance.instanceId} className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{instance.materialDisplayName}</span>
                      <span className="theme-meta">缺失</span>
                    </div>
                    <div className="break-all text-xs text-muted-foreground">{formatMaterialReference(instance.materialId)}</div>
                    <div className="text-xs text-muted-foreground">最近观测：{formatLastSeenAt(instance.lastSeenAt)}</div>
                  </div>

                  <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px_auto] lg:items-end">
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground">受影响复述点</div>
                      <div className="text-sm text-foreground">
                        {countQuery?.isLoading ? "统计中..." : `${recallPointIds.length} 个复述点仍指向该旧实例`}
                      </div>
                      {recallPointIds.length > 0 ? (
                        <div className="break-all text-xs text-muted-foreground">
                          {recallPointIds.slice(0, 6).map((id) => formatRecallPointReference(id)).join(" / ")}
                          {recallPointIds.length > 6 ? " / ..." : ""}
                        </div>
                      ) : (
                        <div className="text-xs text-muted-foreground">该旧实例已无锚点引用。</div>
                      )}
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor={`remap-target-${instance.instanceId}`}>迁移到新实例</Label>
                      <select
                        id={`remap-target-${instance.instanceId}`}
                        className="h-10 w-full rounded-xl border bg-background px-3 text-sm"
                        value={targetInstanceId}
                        onChange={(e) =>
                          setRemapTargets((prev) => ({
                            ...prev,
                            [instance.instanceId]: e.target.value,
                          }))
                        }
                        disabled={presentInstances.length === 0 || bulkRemapM.isPending}
                      >
                        {presentInstances.length === 0 ? <option value="">当前没有可迁移到的新实例</option> : null}
                        {presentInstances.map((item) => (
                          <option key={item.instanceId} value={item.instanceId}>
                            {item.materialDisplayName}（{formatMaterialReference(item.materialId)}）
                          </option>
                        ))}
                      </select>
                    </div>

                    <Button
                      onClick={() => void onRemapMissingInstance(instance.instanceId)}
                      disabled={bulkRemapM.isPending || recallPointIds.length === 0 || !targetInstanceId}
                    >
                      {bulkRemapM.isPending ? "迁移中..." : "迁移复述点"}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>

          {bulkRemapM.error ? <p className="text-sm text-destructive">{formatApiError(bulkRemapM.error)}</p> : null}
        </CardContent>
      </Card>
      ) : null}
    </div>
  )
}

function BookOutlineSetupCard({
  courseMaterials,
  draftValue,
  initialized,
  initializeFromMaterialError,
  initializeFromMaterialPending,
  isPending,
  mutationError,
  onChange,
  onInitializeFromMaterial,
  onInitialize,
  parsedCount,
  validationMessage,
}: {
  courseMaterials: StudyMaterial[]
  draftValue: string
  initialized: boolean
  initializeFromMaterialError: unknown
  initializeFromMaterialPending: boolean
  isPending: boolean
  mutationError: unknown
  onChange: (value: string) => void
  onInitializeFromMaterial: (sourceMaterialId: string) => Promise<void>
  onInitialize: () => Promise<void>
  parsedCount: number
  validationMessage: string | null
}) {
  const [selectedSourceMaterialId, setSelectedSourceMaterialId] = useState("")

  useEffect(() => {
    if (courseMaterials.length === 0) {
      setSelectedSourceMaterialId("")
      return
    }
    setSelectedSourceMaterialId((current) =>
      courseMaterials.some((item) => item.materialId === current) ? current : courseMaterials[0]?.materialId ?? "",
    )
  }, [courseMaterials])

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>书本目录初始化</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-muted-foreground">
          书本材料会维护自己的学习对象树。你可以手工粘贴目录文本，也可以直接复用同一门学科下某个网课材料的学习对象树，系统会把末级节点自动转换为可绑定复述点的书本实例。
        </div>

        {initialized ? (
          <div className="rounded-[1.2rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-700">
            当前书本项目已经存在目录节点和实例。如需重新初始化，请先清理现有目录结构后再执行。
          </div>
        ) : (
          <>
            <div className="space-y-4 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">一键复用网课树</div>
                <p className="text-xs leading-5 text-muted-foreground">把同一门学科下某个网课材料的学习对象树复制成书本目录结构，省掉手动重新录目录。</p>
              </div>

              {courseMaterials.length > 0 ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="bookOutlineSourceMaterial">来源网课材料</Label>
                    <select
                      id="bookOutlineSourceMaterial"
                      className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
                      value={selectedSourceMaterialId}
                      onChange={(event) => setSelectedSourceMaterialId(event.target.value)}
                      disabled={initializeFromMaterialPending}
                    >
                      {courseMaterials.map((material) => (
                        <option key={material.materialId} value={material.materialId}>
                          {material.title}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void onInitializeFromMaterial(selectedSourceMaterialId)}
                      disabled={initializeFromMaterialPending || !selectedSourceMaterialId}
                    >
                      {initializeFromMaterialPending ? "复用中..." : "一键复用网课树"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-xs leading-5 text-muted-foreground">
                  当前学科下还没有可复用的网课材料。先去新建或导入一个网课材料，再回来一键复用。
                </div>
              )}

              {initializeFromMaterialError ? <p className="text-sm text-destructive">{formatApiError(initializeFromMaterialError)}</p> : null}
            </div>

            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <div className="h-px flex-1 bg-border/70" />
              <span>或者手动粘贴目录</span>
              <div className="h-px flex-1 bg-border/70" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="bookOutlineDraft">目录文本</Label>
              <textarea
                id="bookOutlineDraft"
                value={draftValue}
                onChange={(event) => onChange(event.target.value)}
                placeholder={`第一章 极限\n  1.1 函数\n  1.2 极限定义\n第二章 导数\n  2.1 导数概念`}
                rows={10}
                className="min-h-[15rem] w-full resize-y rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>当前已解析 {parsedCount} 行有效目录</span>
              <span>使用两个空格或一个 Tab 表示下一级缩进</span>
            </div>

            {validationMessage ? <p className="text-sm text-destructive">{validationMessage}</p> : null}

            <div className="flex justify-end">
              <Button type="button" onClick={() => void onInitialize()} disabled={isPending || !!validationMessage}>
                {isPending ? "初始化中..." : "初始化书本目录"}
              </Button>
            </div>
          </>
        )}

        {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function MistakeStructureSetupCard({
  sourceMaterials,
  initialized,
  initializeFromMaterialError,
  initializeFromMaterialPending,
  ensureInboxError,
  ensureInboxPending,
  isPending,
  mutationError,
  draftValue,
  onChange,
  onEnsureInbox,
  onInitializeFromMaterial,
  onInitialize,
  parsedCount,
  validationMessage,
}: {
  sourceMaterials: StudyMaterial[]
  initialized: boolean
  initializeFromMaterialError: unknown
  initializeFromMaterialPending: boolean
  ensureInboxError: unknown
  ensureInboxPending: boolean
  isPending: boolean
  mutationError: unknown
  draftValue: string
  onChange: (value: string) => void
  onEnsureInbox: () => Promise<void>
  onInitializeFromMaterial: (sourceMaterialId: string) => Promise<void>
  onInitialize: () => Promise<void>
  parsedCount: number
  validationMessage: string | null
}) {
  const [selectedSourceMaterialId, setSelectedSourceMaterialId] = useState("")

  useEffect(() => {
    if (sourceMaterials.length === 0) {
      setSelectedSourceMaterialId("")
      return
    }
    setSelectedSourceMaterialId((current) =>
      sourceMaterials.some((item) => item.materialId === current) ? current : sourceMaterials[0]?.materialId ?? "",
    )
  }, [sourceMaterials])

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>错题结构初始化</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-muted-foreground">
          错题材料可以先用一个“待整理”入口快速开用，也可以复用同一学科下的网课/书本结构，把错题直接挂到对应章节下面；后续录入、复习、计划统计都会继续沿用这套材料。
        </div>

        {initialized ? (
          <div className="rounded-[1.2rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-700">
            当前错题材料已经存在目录节点和条目。如需重新初始化，请先清理现有结构后再执行。
          </div>
        ) : (
          <>
            <div className="space-y-4 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">快速开用</div>
                <p className="text-xs leading-5 text-muted-foreground">先创建一个“待整理”入口，适合立刻开始收集错题，后面再慢慢细分。</p>
              </div>
              <div className="flex justify-end">
                <Button type="button" variant="outline" onClick={() => void onEnsureInbox()} disabled={ensureInboxPending}>
                  {ensureInboxPending ? "创建中..." : "创建待整理入口"}
                </Button>
              </div>
              {ensureInboxError ? <p className="text-sm text-destructive">{formatApiError(ensureInboxError)}</p> : null}
            </div>

            <div className="space-y-4 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">一键复用学科结构</div>
                <p className="text-xs leading-5 text-muted-foreground">把同一学科下的网课或书本材料结构复制过来，后续错题就能直接按章节归档。</p>
              </div>
              {sourceMaterials.length > 0 ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="mistakeStructureSourceMaterial">来源材料</Label>
                    <select
                      id="mistakeStructureSourceMaterial"
                      className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
                      value={selectedSourceMaterialId}
                      onChange={(event) => setSelectedSourceMaterialId(event.target.value)}
                      disabled={initializeFromMaterialPending}
                    >
                      {sourceMaterials.map((material) => (
                        <option key={material.materialId} value={material.materialId}>
                          {material.title}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void onInitializeFromMaterial(selectedSourceMaterialId)}
                      disabled={initializeFromMaterialPending || !selectedSourceMaterialId}
                    >
                      {initializeFromMaterialPending ? "复用中..." : "一键复用章节结构"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-xs leading-5 text-muted-foreground">
                  当前学科下还没有可复用的网课或书本材料。先去创建或整理一个来源材料，再回来复用结构。
                </div>
              )}
              {initializeFromMaterialError ? <p className="text-sm text-destructive">{formatApiError(initializeFromMaterialError)}</p> : null}
            </div>

            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <div className="h-px flex-1 bg-border/70" />
              <span>或者手动粘贴错题目录</span>
              <div className="h-px flex-1 bg-border/70" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="mistakeOutlineDraft">目录文本</Label>
              <textarea
                id="mistakeOutlineDraft"
                value={draftValue}
                onChange={(event) => onChange(event.target.value)}
                placeholder={`极限\n  函数极限\n  数列极限\n导数\n  导数定义\n  微分中值定理`}
                rows={10}
                className="min-h-[15rem] w-full resize-y rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>当前已解析 {parsedCount} 行有效目录</span>
              <span>使用两个空格或一个 Tab 表示下一级缩进</span>
            </div>

            {validationMessage ? <p className="text-sm text-destructive">{validationMessage}</p> : null}

            <div className="flex justify-end">
              <Button type="button" onClick={() => void onInitialize()} disabled={isPending || !!validationMessage}>
                {isPending ? "初始化中..." : "初始化错题结构"}
              </Button>
            </div>
          </>
        )}

        {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function SettingsScopeCard(props: {
  isSubjectRoot: boolean
  materialTitle: string
  materialType: StudyMaterial["materialType"]
  onOpenSubjectSettings?: () => void
  subjectTitle: string
}) {
  const { isSubjectRoot, materialTitle, materialType, onOpenSubjectSettings, subjectTitle } = props

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>当前范围</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-xs text-muted-foreground">学科</div>
              <div className="mt-1 text-sm font-semibold text-foreground">{subjectTitle || "当前学科"}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">当前材料</div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-foreground">{materialTitle || "当前材料"}</span>
                <span className="theme-meta-strong">{formatStudyMaterialTypeLabel(materialType)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="theme-status-surface rounded-[1.2rem] border border-border/70 px-4 py-4 text-muted-foreground">
          {isSubjectRoot
            ? "这里维护学科标题和学科下的材料编排。当前这套导入、目录初始化、层推进和缺失修复配置，实际作用在默认网课材料上。"
            : "这里维护当前材料自己的导入、目录初始化、层推进和缺失修复配置。学科标题和材料编排仍然由学科设置统一管理。"}
        </div>

        {!isSubjectRoot && onOpenSubjectSettings ? (
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={onOpenSubjectSettings}>
              回到学科设置
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function SubjectMaterialsCard({
  createError,
  createPending,
  currentProjectId,
  error,
  isLoading,
  isSubjectRoot,
  materials,
  onCreateMaterial,
  onOpenMaterial,
  subjectTitle,
}: {
  createError: unknown
  createPending: boolean
  currentProjectId: string
  error: unknown
  isLoading: boolean
  isSubjectRoot: boolean
  materials: StudyMaterial[]
  onCreateMaterial: (materialType: StudyMaterial["materialType"], title: string) => Promise<void>
  onOpenMaterial: (material: StudyMaterial, target: "workbench" | "settings") => void
  subjectTitle: string
}) {
  const [draftType, setDraftType] = useState<StudyMaterial["materialType"] | null>(null)
  const [draftTitle, setDraftTitle] = useState("")

  function beginCreate(materialType: StudyMaterial["materialType"]) {
    setDraftType(materialType)
    setDraftTitle(`${subjectTitle || "当前学科"}·${formatStudyMaterialTypeLabel(materialType)}`)
  }

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>学习材料</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface rounded-[1.2rem] border border-border/70 px-4 py-4 text-muted-foreground">
          {isSubjectRoot
            ? `“${subjectTitle || "当前学科"}”下面的每份材料都可以拥有自己的兼容工作台。这样网课、书本、错题和零散知识可以分开整理，同时仍然挂在同一门学科里。`
            : `你现在在“${subjectTitle || "当前学科"}”的某个材料里，这里也可以直接切到兄弟材料，或者继续往这个学科下面新增材料。`}
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">正在加载材料清单...</p> : null}
        {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}
        {createError ? <p className="text-sm text-destructive">{formatApiError(createError)}</p> : null}

        <div className="flex flex-wrap gap-2">
          {(["COURSE", "BOOK", "LOOSE_POINTS", "MISTAKE_BOOK"] as const).map((materialType) => (
            <Button key={materialType} type="button" variant="outline" disabled={createPending} onClick={() => beginCreate(materialType)}>
              新建{formatStudyMaterialTypeLabel(materialType)}
            </Button>
          ))}
        </div>

        {draftType ? (
          <div className="space-y-3 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">创建{formatStudyMaterialTypeLabel(draftType)}</div>
              <p className="text-xs leading-5 text-muted-foreground">{describeStudyMaterialHint(draftType)}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="subjectMaterialTitle">材料名称</Label>
              <Input
                id="subjectMaterialTitle"
                value={draftTitle}
                maxLength={120}
                disabled={createPending}
                onChange={(event) => setDraftTitle(event.target.value)}
                placeholder={`${subjectTitle || "当前学科"}·${formatStudyMaterialTypeLabel(draftType)}`}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={createPending || !draftTitle.trim()}
                onClick={() => {
                  void (async () => {
                    try {
                      await onCreateMaterial(draftType, draftTitle.trim())
                      setDraftType(null)
                      setDraftTitle("")
                    } catch {
                      // keep draft so the user can retry after the error message
                    }
                  })()
                }}
              >
                {createPending ? "创建中..." : "确认创建"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={createPending}
                onClick={() => {
                  setDraftType(null)
                  setDraftTitle("")
                }}
              >
                取消
              </Button>
            </div>
          </div>
        ) : null}

        {!isLoading && materials.length === 0 ? (
          <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">当前学科还没有材料。</div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2">
          {materials.map((material) => (
            <div key={material.materialId} className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">{material.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">各自拥有独立兼容工作台和导入入口</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {material.compatibilityProjectId === currentProjectId ? <span className="theme-meta-strong">当前材料</span> : null}
                  <span className="theme-meta-strong">{formatStudyMaterialTypeLabel(material.materialType)}</span>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">{describeStudyMaterialHint(material.materialType)}</p>
              {material.compatibilityProjectId ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" size="sm" onClick={() => onOpenMaterial(material, "workbench")}>
                    进入工作台
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => onOpenMaterial(material, "settings")}>
                    材料设置
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function BasicInfoCard({
  actionableMissingInstanceCount,
  baiduNetdiskEnabled,
  browserLocalMediaEnabled,
  canChooseDirectory,
  canClearDirectory,
  canRequestDirectoryPermission,
  directoryAction,
  directoryBinding,
  directoryBusy,
  directoryPermission,
  entityLabel,
  entityPlaceholder,
  entitySaveLabel,
  entityTitle,
  importError,
  isLoading,
  isPending,
  isSubjectRoot,
  materialTitle,
  materialType,
  onOpenSubjectSettings,
  projectType,
  queryError,
  rollUpStrategy,
  saveError,
  rollUpStrategyError,
  rollUpStrategySaving,
  subjectTitle,
  onAuthorizeDirectory,
  onChangeRollUpStrategy,
  onClearDirectoryBinding,
  onOpenBaiduImport,
  onImportAuthorizedDirectory,
  onRequestDirectoryPermission,
  onSave,
  layerConfigSection,
}: {
  actionableMissingInstanceCount: number
  baiduNetdiskEnabled: boolean
  browserLocalMediaEnabled: boolean
  canChooseDirectory: boolean
  canClearDirectory: boolean
  canRequestDirectoryPermission: boolean
  directoryAction: "authorize" | "request" | "clear" | "import" | null
  directoryBinding: ReturnType<typeof useProjectDirectoryBinding>
  directoryBusy: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
  entityLabel: string
  entityPlaceholder: string
  entitySaveLabel: string
  entityTitle: string
  importError: unknown
  isLoading: boolean
  isPending: boolean
  isSubjectRoot: boolean
  materialTitle: string
  materialType: StudyMaterial["materialType"]
  onOpenSubjectSettings?: () => void
  projectType: ProjectType
  queryError: unknown
  rollUpStrategy: RollUpStrategy
  saveError: unknown
  rollUpStrategyError: unknown
  rollUpStrategySaving: boolean
  subjectTitle: string
  onAuthorizeDirectory: () => Promise<void>
  onChangeRollUpStrategy: (nextStrategy: RollUpStrategy) => Promise<void>
  onClearDirectoryBinding: () => Promise<void>
  onOpenBaiduImport: () => void
  onImportAuthorizedDirectory: (silentSuccess?: boolean) => Promise<void>
  onRequestDirectoryPermission: () => Promise<void>
  onSave: (title: string) => Promise<void>
  layerConfigSection: ReactNode
}) {
  const [titleDraft, setTitleDraft] = useState(entityTitle)

  useEffect(() => {
    setTitleDraft(entityTitle)
  }, [entityTitle])

  const trimmedTitle = titleDraft.trim()
  const canSave = !isLoading && !isPending && !!trimmedTitle && trimmedTitle !== entityTitle.trim()

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>基本信息</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-0 text-sm">
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.75fr)] lg:items-start">
          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">{entityLabel}名称</div>
            </div>
            <form
              className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
              onSubmit={(event) => {
                event.preventDefault()
                if (!canSave) return
                void onSave(trimmedTitle)
              }}
            >
              <div>
                <Label htmlFor="projectTitle" className="sr-only">
                  新名称
                </Label>
                <Input
                  id="projectTitle"
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  placeholder={entityPlaceholder}
                  disabled={isLoading || isPending}
                />
              </div>
              <div className="flex items-center justify-end">
                <Button type="submit" disabled={!canSave} className="w-full md:w-auto">
                  {isPending ? "保存中..." : entitySaveLabel}
                </Button>
              </div>
            </form>
            {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
            {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">{isSubjectRoot ? "默认材料" : "所属学科"}</div>
            </div>
            <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-3">
              {isSubjectRoot ? (
                <>
                  <div className="text-sm font-semibold text-foreground">{materialTitle || "默认网课材料"}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatStudyMaterialTypeLabel(materialType)} · {formatProjectTypeLabel(projectType)}</div>
                </>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-foreground">{subjectTitle || "当前学科"}</div>
                    <div className="mt-1 text-xs text-muted-foreground">当前材料类型：{formatStudyMaterialTypeLabel(materialType)}</div>
                  </div>
                  {onOpenSubjectSettings ? (
                    <Button type="button" variant="outline" size="sm" onClick={onOpenSubjectSettings}>
                      学科设置
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">{isSubjectRoot ? "默认网课材料" : `当前${formatStudyMaterialTypeLabel(materialType)}材料`}</div>
          </div>

          {projectType === "COURSE" ? (
            <div className="space-y-3">
              {browserLocalMediaEnabled ? (
                <div className="theme-status-surface rounded-[1.35rem] border border-border/70 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="theme-meta-strong">本地素材目录</span>
                        <span
                          className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeDirectoryPermissionTone(directoryPermission)}`}
                        >
                          {describeDirectoryPermission(directoryPermission)}
                        </span>
                      </div>
                      <div className="text-sm text-foreground">
                        {directoryBinding.handleName ? directoryBinding.handleName : `当前${isSubjectRoot ? "默认网课材料" : "材料"}还没有绑定浏览器目录。`}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      {directoryPermission === "granted" ? (
                        <>
                          <Button type="button" onClick={() => void onImportAuthorizedDirectory()} disabled={directoryBusy}>
                            {directoryAction === "import" ? "同步中..." : "同步目录内容"}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void onAuthorizeDirectory()}
                            disabled={!canChooseDirectory || directoryBusy}
                          >
                            {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                          </Button>
                        </>
                      ) : null}

                      {(directoryPermission === "missing" || directoryPermission === "unsupported") ? (
                        <Button type="button" onClick={() => void onAuthorizeDirectory()} disabled={!canChooseDirectory || directoryBusy}>
                          {directoryAction === "authorize" ? "打开目录选择器..." : "选择目录"}
                        </Button>
                      ) : null}

                      {(directoryPermission === "prompt" || directoryPermission === "denied") ? (
                        <>
                          <Button
                            type="button"
                            onClick={() => void onRequestDirectoryPermission()}
                            disabled={!canRequestDirectoryPermission || directoryBusy}
                          >
                            {directoryAction === "request" ? "请求中..." : "继续授权"}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void onAuthorizeDirectory()}
                            disabled={!canChooseDirectory || directoryBusy}
                          >
                            {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                          </Button>
                        </>
                      ) : null}

                      {(directoryPermission === "granted" || directoryPermission === "prompt" || directoryPermission === "denied") &&
                      canClearDirectory ? (
                        <Button
                          type="button"
                          variant="ghost"
                          className="text-muted-foreground"
                          onClick={() => void onClearDirectoryBinding()}
                          disabled={!canClearDirectory || directoryBusy}
                        >
                          {directoryAction === "clear" ? "清除中..." : "清除本地绑定"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
                  当前部署没有开启浏览器本地目录模式。
                </div>
              )}

              {baiduNetdiskEnabled ? (
                <div className="theme-status-surface rounded-[1.35rem] border border-border/70 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="theme-meta-strong">百度网盘视频</span>
                        <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
                          已启用
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        支持在当前{isSubjectRoot ? "默认网课材料" : "材料"}里浏览百度网盘目录、导入视频并按实例播放；字幕会按同目录同名规则自动识别。
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      <Button type="button" onClick={onOpenBaiduImport}>
                        从百度网盘导入
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
              {projectType === "BOOK"
                ? `当前${isSubjectRoot ? "书本入口" : "书本材料"}不依赖浏览器目录授权；请使用“书本目录初始化”把目录文本转换为学习对象树。`
                : projectType === "MISTAKE_BOOK"
                  ? `当前${isSubjectRoot ? "错题入口" : "错题材料"}不接入素材目录；你可以先创建“待整理”入口，或复用学科内的网课/书本结构来承接错题。`
                : `当前${isSubjectRoot ? "零散知识入口" : "零散知识材料"}不接入素材目录，也不会维护学习对象树。`}
            </div>
          )}

          {projectType === "COURSE" && directoryBinding.error ? <p className="text-sm text-destructive">{directoryBinding.error}</p> : null}
          {projectType === "COURSE" && !directoryBinding.supported ? (
            <p className="text-sm text-muted-foreground">当前浏览器不支持目录授权。首版建议使用桌面 Chrome 或 Edge。</p>
          ) : null}
          {projectType === "COURSE" && importError ? <p className="text-sm text-destructive">{formatApiError(importError)}</p> : null}
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-4">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">上推策略</div>
            <p className="text-sm text-muted-foreground">
              当前材料使用“{getRollUpStrategyLabel(rollUpStrategy)}”。{getRollUpStrategyDescription(rollUpStrategy)}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="rollUpStrategy">材料级推进方式</Label>
            <select
              id="rollUpStrategy"
              aria-label="选择上推策略"
              className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
              value={rollUpStrategy}
              disabled={rollUpStrategySaving}
              onChange={(event) => {
                const nextStrategy = event.target.value as RollUpStrategy
                void onChangeRollUpStrategy(nextStrategy)
              }}
            >
              <option value="MANUAL">仅手动上推</option>
              <option value="THRESHOLD_AUTO">阈值自动上推</option>
              <option value="LEARNING_OBJECT_ISOMORPHIC">学习对象树同构上推</option>
            </select>
          </div>

          <div className="rounded-[1.1rem] border border-border/70 bg-muted/15 p-4 text-sm text-muted-foreground">
            {rollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC"
              ? actionableMissingInstanceCount > 0
                ? `当前有 ${actionableMissingInstanceCount} 个待迁移的缺失实例，同构上推和学习任务提交都会先被门禁拦住。请先完成下方修复。`
                : "当前没有待迁移的缺失实例，同构上推会在队列清空后按对象树自动扫描推进。"
              : rollUpStrategy === "MANUAL"
                ? "你可以继续保留各层阈值配置，但系统不会自动触发上推。"
                : "各层的节点阈值、复述点阈值和阈值开关都在下面的层配置里生效。"}
          </div>

          {rollUpStrategyError ? <p className="text-sm text-destructive">{formatApiError(rollUpStrategyError)}</p> : null}
        </section>

        <div className="border-t border-border/60" />

        {layerConfigSection}
      </CardContent>
    </Card>
  )
}

function DangerZoneCard(props: {
  actionLabel: string
  actionPendingLabel: string
  confirmationLabel: string
  deleteError: unknown
  description: string
  isPending: boolean
  onDelete: () => Promise<void>
  targetTitle: string
}) {
  const { actionLabel, actionPendingLabel, confirmationLabel, deleteError, description, isPending, onDelete, targetTitle } = props
  const [confirmation, setConfirmation] = useState("")

  useEffect(() => {
    setConfirmation("")
  }, [targetTitle])

  const matches = confirmation.trim() === targetTitle.trim()

  return (
    <Card className="theme-card border-destructive/20">
      <CardHeader>
        <CardTitle>危险操作</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-destructive/15 bg-destructive/5 px-4 py-4 text-muted-foreground">{description}</div>

        <div className="grid gap-2">
          <Label htmlFor="danger-zone-confirmation">{confirmationLabel}</Label>
          <Input
            id="danger-zone-confirmation"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={targetTitle || confirmationLabel}
            disabled={isPending}
          />
          <p className="text-xs text-muted-foreground">
            请输入 <span className="font-semibold text-foreground">{targetTitle}</span> 完成确认。
          </p>
        </div>

        <div className="flex justify-end">
          <Button type="button" variant="destructive" disabled={isPending || !matches || !targetTitle.trim()} onClick={() => void onDelete()}>
            {isPending ? actionPendingLabel : actionLabel}
          </Button>
        </div>

        {deleteError ? <p className="text-sm text-destructive">{formatApiError(deleteError)}</p> : null}
      </CardContent>
    </Card>
  )
}

const SAVED_API_KEY_MASK = "********"

function SavedApiKeyInput({
  id,
  draftValue,
  onDraftChange,
  savedApiKeyConfigured,
  disabled,
  emptyPlaceholder,
  savedPlaceholder,
}: {
  id: string
  draftValue: string
  onDraftChange: (value: string) => void
  savedApiKeyConfigured: boolean
  disabled: boolean
  emptyPlaceholder: string
  savedPlaceholder: string
}) {
  const [isEditingSavedKey, setIsEditingSavedKey] = useState(false)

  useEffect(() => {
    setIsEditingSavedKey(false)
  }, [id, savedApiKeyConfigured])

  const showSavedMask = savedApiKeyConfigured && !isEditingSavedKey && !draftValue.trim()

  return (
    <Input
      id={id}
      type="password"
      value={showSavedMask ? SAVED_API_KEY_MASK : draftValue}
      onFocus={() => {
        if (showSavedMask && !disabled) {
          setIsEditingSavedKey(true)
          onDraftChange("")
        }
      }}
      onBlur={() => {
        if (!draftValue.trim()) {
          setIsEditingSavedKey(false)
        }
      }}
      onChange={(event) => onDraftChange(event.target.value)}
      placeholder={savedApiKeyConfigured ? savedPlaceholder : emptyPlaceholder}
      disabled={disabled}
      autoComplete="off"
    />
  )
}

function GlobalLlmSettingsCard({
  title,
  saveLabel,
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  title: string
  saveLabel: string
  settings:
    | {
        baseUrl: string
        modelName: string
        promptAssemblyMode: LlmPromptAssemblyMode
        savedApiKeyConfigured: boolean
        savedApiKeyPreview: string | null
        llmConfigured: boolean
        storyGenerationConfigured: boolean
        llmSource: "user" | "global" | "env" | "none"
      }
    | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode; apiKey?: string }) => Promise<void>
  onClearApiKey: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode }) => Promise<void>
}) {
  const [baseUrlDraft, setBaseUrlDraft] = useState("")
  const [modelDraft, setModelDraft] = useState("")
  const [apiKeyDraft, setApiKeyDraft] = useState("")
  const [promptAssemblyModeDraft, setPromptAssemblyModeDraft] = useState<LlmPromptAssemblyMode>("system")

  useEffect(() => {
    setBaseUrlDraft(settings?.baseUrl ?? "")
    setModelDraft(settings?.modelName ?? "")
    setApiKeyDraft("")
    setPromptAssemblyModeDraft(settings?.promptAssemblyMode ?? "system")
  }, [settings?.baseUrl, settings?.modelName, settings?.promptAssemblyMode])

  const trimmedBaseUrl = baseUrlDraft.trim()
  const trimmedModel = modelDraft.trim()
  const trimmedApiKey = apiKeyDraft.trim()
  const canSave =
    !isLoading &&
    !isPending &&
    !!trimmedBaseUrl &&
    !!trimmedModel &&
    (
      trimmedBaseUrl !== (settings?.baseUrl ?? "") ||
      trimmedModel !== (settings?.modelName ?? "") ||
      promptAssemblyModeDraft !== (settings?.promptAssemblyMode ?? "system") ||
      !!trimmedApiKey
    )
  const canClearApiKey = !isLoading && !isPending && !!settings?.savedApiKeyConfigured

  return (
    <Card className="theme-card">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <CardTitle>{title}</CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLlmSourceTone(settings?.llmSource ?? "none")}`}
            >
              {describeLlmSource(settings?.llmSource ?? "none")}
            </span>
            <span className="theme-meta px-3 py-1.5 text-xs">
              {settings?.llmConfigured ? "LLM 已可用" : "LLM 未可用"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label htmlFor="globalLlmBaseUrl">Base URL</Label>
              <Input
                id="globalLlmBaseUrl"
                value={baseUrlDraft}
                onChange={(event) => setBaseUrlDraft(event.target.value)}
                placeholder="https://api.openai.com/v1"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="globalLlmModel">模型名</Label>
              <Input
                id="globalLlmModel"
                value={modelDraft}
                onChange={(event) => setModelDraft(event.target.value)}
                placeholder="gpt-4o-mini"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="globalLlmApiKey">API 密钥</Label>
              <SavedApiKeyInput
                id="globalLlmApiKey"
                draftValue={apiKeyDraft}
                onDraftChange={setApiKeyDraft}
                savedApiKeyConfigured={!!settings?.savedApiKeyConfigured}
                emptyPlaceholder="输入新的 API Key"
                savedPlaceholder="输入新的 API Key"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label>提示拼接模式</Label>
              <PromptAssemblyModeSelector
                value={promptAssemblyModeDraft}
                onChange={setPromptAssemblyModeDraft}
                disabled={isLoading || isPending}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={!canSave}
              onClick={() =>
                void onSave({
                  baseUrl: trimmedBaseUrl,
                  modelName: trimmedModel,
                  promptAssemblyMode: promptAssemblyModeDraft,
                  apiKey: trimmedApiKey || undefined,
                })
              }
            >
              {isPending ? "保存中..." : saveLabel}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!canClearApiKey}
              onClick={() =>
                void onClearApiKey({
                  baseUrl: trimmedBaseUrl || settings?.baseUrl || "",
                  modelName: trimmedModel || settings?.modelName || "",
                  promptAssemblyMode: promptAssemblyModeDraft,
                })
              }
            >
              清除已保存密钥
            </Button>
          </div>
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">加载{title}中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function UserLlmSettingsCard({
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  settings:
    | {
        baseUrl: string
        modelName: string
        promptAssemblyMode: LlmPromptAssemblyMode
        savedApiKeyConfigured: boolean
        savedApiKeyPreview: string | null
        llmConfigured: boolean
        storyGenerationConfigured: boolean
        llmSource: "user" | "global" | "env" | "none"
      }
    | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode; apiKey?: string }) => Promise<void>
  onClearApiKey: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode }) => Promise<void>
}) {
  const [baseUrlDraft, setBaseUrlDraft] = useState("")
  const [modelDraft, setModelDraft] = useState("")
  const [apiKeyDraft, setApiKeyDraft] = useState("")
  const [promptAssemblyModeDraft, setPromptAssemblyModeDraft] = useState<LlmPromptAssemblyMode>("system")

  useEffect(() => {
    setBaseUrlDraft(settings?.baseUrl ?? "")
    setModelDraft(settings?.modelName ?? "")
    setApiKeyDraft("")
    setPromptAssemblyModeDraft(settings?.promptAssemblyMode ?? "system")
  }, [settings?.baseUrl, settings?.modelName, settings?.promptAssemblyMode])

  const trimmedBaseUrl = baseUrlDraft.trim()
  const trimmedModel = modelDraft.trim()
  const trimmedApiKey = apiKeyDraft.trim()
  const canSave =
    !isLoading &&
    !isPending &&
    !!trimmedBaseUrl &&
    !!trimmedModel &&
    (
      trimmedBaseUrl !== (settings?.baseUrl ?? "") ||
      trimmedModel !== (settings?.modelName ?? "") ||
      promptAssemblyModeDraft !== (settings?.promptAssemblyMode ?? "system") ||
      !!trimmedApiKey
    )
  const canClearApiKey = !isLoading && !isPending && !!settings?.savedApiKeyConfigured

  return (
    <Card className="theme-card">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <CardTitle>我的 LLM 设置</CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLlmSourceTone(settings?.llmSource ?? "none")}`}
            >
              {describeLlmSource(settings?.llmSource ?? "none")}
            </span>
            <span className="theme-meta px-3 py-1.5 text-xs">
              {settings?.llmConfigured ? "当前账号已就绪" : "当前账号未配置"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label htmlFor="userLlmBaseUrl">Base URL</Label>
              <Input
                id="userLlmBaseUrl"
                value={baseUrlDraft}
                onChange={(event) => setBaseUrlDraft(event.target.value)}
                placeholder="https://api.openai.com/v1"
                disabled={isLoading || isPending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="userLlmModel">模型名</Label>
              <Input
                id="userLlmModel"
                value={modelDraft}
                onChange={(event) => setModelDraft(event.target.value)}
                placeholder="gpt-4o-mini"
                disabled={isLoading || isPending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="userLlmApiKey">API 密钥</Label>
              <SavedApiKeyInput
                id="userLlmApiKey"
                draftValue={apiKeyDraft}
                onDraftChange={setApiKeyDraft}
                savedApiKeyConfigured={!!settings?.savedApiKeyConfigured}
                emptyPlaceholder="输入你的 API Key"
                savedPlaceholder="输入你的 API Key"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label>提示拼接模式</Label>
              <PromptAssemblyModeSelector
                value={promptAssemblyModeDraft}
                onChange={setPromptAssemblyModeDraft}
                disabled={isLoading || isPending}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={!canSave}
              onClick={() =>
                void onSave({
                  baseUrl: trimmedBaseUrl,
                  modelName: trimmedModel,
                  promptAssemblyMode: promptAssemblyModeDraft,
                  apiKey: trimmedApiKey || undefined,
                })
              }
            >
              {isPending ? "保存中..." : "保存到我的账号"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!canClearApiKey}
              onClick={() =>
                void onClearApiKey({
                  baseUrl: trimmedBaseUrl || settings?.baseUrl || "",
                  modelName: trimmedModel || settings?.modelName || "",
                  promptAssemblyMode: promptAssemblyModeDraft,
                })
              }
            >
              清除我的密钥
            </Button>
          </div>
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">加载我的 LLM 设置中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function LayerConfigEditor({
  canSave,
  embedded: _embedded = false,
  existingLayerIndexes,
  initialConfig,
  knownLayerIndexes,
  layersError,
  mutationError,
  onSave,
  onSelectedLayerIndexChange,
  projectConfigError,
  rollUpStrategy,
  selectedLayerExists,
  selectedLayerHasSavedConfig,
  saving,
  selectedLayerIndex,
}: {
  canSave: boolean
  embedded?: boolean
  existingLayerIndexes: number[]
  initialConfig: {
    reviewChainTemplate: ReviewChainTemplateItem[]
    aggregationKNode: number
    aggregationKPoint: number
    thresholdRollUpEnabled: boolean
  }
  knownLayerIndexes: number[]
  layersError: unknown
  mutationError: unknown
  onSave: (payload: {
    kNode: number
    kPoint: number
    reviewChainTemplate: ReviewChainTemplateItem[]
    thresholdRollUpEnabled: boolean
  }) => Promise<void>
  onSelectedLayerIndexChange: (layerIndex: number) => void
  projectConfigError: unknown
  rollUpStrategy: RollUpStrategy
  selectedLayerExists: boolean
  selectedLayerHasSavedConfig: boolean
  saving: boolean
  selectedLayerIndex: number
}) {
  const [cfgKNode, setCfgKNode] = useState(() => String(initialConfig.aggregationKNode))
  const [cfgKPoint, setCfgKPoint] = useState(() => String(initialConfig.aggregationKPoint))
  const [cfgThresholdRollUpEnabled, setCfgThresholdRollUpEnabled] = useState(() => initialConfig.thresholdRollUpEnabled)
  const [cfgTemplateItems, setCfgTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(initialConfig.reviewChainTemplate))
  const [cfgErr, setCfgErr] = useState<string | null>(null)
  const [pendingTemplateKind, setPendingTemplateKind] = useState<"" | "CONVERGENCE" | "REVIEW_TASK">("")
  const thresholdControlsActive = rollUpStrategy === "THRESHOLD_AUTO"
  const layerStatusText = selectedLayerExists
    ? selectedLayerHasSavedConfig
      ? "当前层已经存在，下面显示的是它的已保存配置。"
      : "当前层已经存在，但还没有专属配置，当前显示的是系统默认值。"
    : selectedLayerHasSavedConfig
      ? "当前层还不存在，下面显示的是它的预配置；该层创建后会自动使用。"
      : "当前层还不存在，当前显示的是系统默认值；保存后会成为这层的预配置。"

  function onAppendTemplateItem() {
    if (!pendingTemplateKind) return
    setCfgTemplateItems((prev) => [...prev, createTemplateEditorItem(pendingTemplateKind)])
    setPendingTemplateKind("")
  }

  async function onSaveLayerConfig() {
    setCfgErr(null)

    const kNode = Number(cfgKNode)
    const kPoint = Number(cfgKPoint)
    if (!Number.isInteger(kNode) || kNode < 1) {
      setCfgErr("节点阈值必须是大于等于 1 的整数")
      return
    }
    if (!Number.isInteger(kPoint) || kPoint < 1) {
      setCfgErr("复述点阈值必须是大于等于 1 的整数")
      return
    }

    const items: ReviewChainTemplateItem[] = []
    let hasConvergence = false

    for (const item of cfgTemplateItems) {
      if (item.kind === "CONVERGENCE") {
        hasConvergence = true
        items.push({ kind: "CONVERGENCE" })
        continue
      }

      const count = Number(item.count)
      if (!Number.isInteger(count) || count < 1) {
        setCfgErr("复习任务次数必须是大于等于 1 的整数")
        return
      }
      items.push(count === 1 ? { kind: "REVIEW_TASK" } : { kind: "REVIEW_TASK", count })
    }

    if (items.length === 0) {
      setCfgErr("模板不能为空")
      return
    }
    if (!hasConvergence) {
      setCfgErr("模板里至少需要一个收敛步骤")
      return
    }

    await onSave({ kNode, kPoint, reviewChainTemplate: items, thresholdRollUpEnabled: cfgThresholdRollUpEnabled })
  }

  const header = (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-1">
        {_embedded ? <div className="text-sm font-semibold text-foreground">层配置</div> : <CardTitle>层配置</CardTitle>}
        <p className="text-sm text-muted-foreground">{layerStatusText}</p>
      </div>

      <div className="w-full max-w-[360px] shrink-0 space-y-3">
        <div className="space-y-2">
          <Label htmlFor="configLayer">已知层</Label>
          <select
            id="configLayer"
            aria-label="选择已知层"
            className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
            value={String(selectedLayerIndex)}
            onChange={(e) => {
              const next = Number(e.target.value)
              if (!Number.isInteger(next) || next < 0) return
              onSelectedLayerIndexChange(next)
            }}
            disabled={saving}
          >
            {knownLayerIndexes.map((idx) => (
              <option key={idx} value={idx}>
                第 {idx} 层{existingLayerIndexes.includes(idx) ? "（已创建）" : "（未创建）"}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )

  const content = (
    <div className="space-y-4 text-sm">
      {!thresholdControlsActive ? (
        <div className="rounded-[1.1rem] border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900">
          当前材料使用“{getRollUpStrategyLabel(rollUpStrategy)}”。下面的阈值参数会继续保存，但只有切回“阈值自动上推”时才会参与自动推进。
        </div>
      ) : null}
      <div className="grid gap-4">
        <div className="grid gap-4 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="kNode">节点阈值</Label>
            <Input id="kNode" value={cfgKNode} onChange={(e) => setCfgKNode(e.target.value)} disabled={saving} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="kPoint">复述点阈值</Label>
            <Input id="kPoint" value={cfgKPoint} onChange={(e) => setCfgKPoint(e.target.value)} disabled={saving} />
          </div>
        </div>

        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <Label>阈值自动上推</Label>
              <p className="text-xs text-muted-foreground">
                {!thresholdControlsActive
                  ? "当前策略不是“阈值自动上推”，这里先作为保留配置展示。"
                  : cfgThresholdRollUpEnabled
                    ? "达到节点数或复述点阈值后，系统会自动进入聚合周期。"
                    : "已关闭自动阈值上推。达到阈值后，候选任务会继续保留在这一层，直到你手动上推或重新开启。"}
              </p>
            </div>
            <Button
              type="button"
              variant={cfgThresholdRollUpEnabled ? "outline" : "default"}
              onClick={() => setCfgThresholdRollUpEnabled((prev) => !prev)}
              disabled={saving || !thresholdControlsActive}
            >
              {!thresholdControlsActive ? "当前策略下不生效" : cfgThresholdRollUpEnabled ? "已开启，点击关闭" : "已关闭，点击开启"}
            </Button>
          </div>
        </div>

        <div className="space-y-3 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
          <Label>复习链模板</Label>

          <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background/90">
            {cfgTemplateItems.length === 0 ? (
              <div className="px-4 py-6 text-sm text-muted-foreground">
                还没有模板步骤，请在下方选择步骤类型后点击加号。
              </div>
            ) : null}

            {cfgTemplateItems.map((item, index) => (
              <div
                key={item.id}
                className="border-t border-border/70 p-4 first:border-t-0"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex items-start gap-3">
                    <span className="inline-flex items-center rounded-full border border-[#d8e3ee] bg-[#f6f9fc] px-2.5 py-1 text-xs font-semibold text-[#5f7790]">
                        第 {index + 1} 步
                    </span>
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-foreground">{item.kind === "CONVERGENCE" ? "收敛" : "复习任务"}</div>
                      <div className="text-xs text-muted-foreground">
                        {item.kind === "CONVERGENCE"
                          ? "完成一轮后决定是否继续生成复习任务。"
                          : "在当前范围上直接生成待执行复习任务。"}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                    {item.kind === "REVIEW_TASK" ? (
                      <div className="w-full max-w-[220px] space-y-2">
                        <Label htmlFor={`template-count-${item.id}`}>次数</Label>
                        <Input
                          id={`template-count-${item.id}`}
                          inputMode="numeric"
                          value={item.count}
                          onChange={(e) =>
                            setCfgTemplateItems((prev) =>
                              prev.map((current) =>
                                current.id === item.id
                                  ? {
                                      ...current,
                                      count: e.target.value,
                                    }
                                  : current,
                              ),
                            )
                          }
                          disabled={saving}
                        />
                      </div>
                    ) : (
                      <div className="rounded-full border border-border/60 bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground">这个步骤没有额外参数</div>
                    )}

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setCfgTemplateItems((prev) => prev.filter((current) => current.id !== item.id))}
                      disabled={saving}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="shrink-0"
              onClick={onAppendTemplateItem}
              disabled={saving || !pendingTemplateKind}
              aria-label="追加模板步骤"
            >
              <span className="text-lg leading-none">+</span>
            </Button>
            <div className="w-full sm:max-w-[220px]">
              <Label htmlFor="pendingTemplateKind" className="sr-only">
                选择步骤类型
              </Label>
              <select
                id="pendingTemplateKind"
                aria-label="选择步骤类型"
                className="h-10 w-full rounded-xl border bg-background px-4 text-sm"
                value={pendingTemplateKind}
                onChange={(e) => setPendingTemplateKind(e.target.value as "" | "CONVERGENCE" | "REVIEW_TASK")}
                disabled={saving}
              >
                <option value="">选择类型</option>
                <option value="CONVERGENCE">收敛</option>
                <option value="REVIEW_TASK">复习任务</option>
              </select>
            </div>
          </div>

        </div>

        <div className="flex justify-end">
          <Button onClick={() => void onSaveLayerConfig()} disabled={saving || !canSave}>
            {saving ? "保存中..." : "保存配置"}
          </Button>
        </div>

        {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}
        {projectConfigError ? <p className="text-sm text-destructive">{formatApiError(projectConfigError)}</p> : null}
        {cfgErr ? <p className="text-sm text-destructive">{cfgErr}</p> : null}
        {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
      </div>
    </div>
  )

  if (_embedded) {
    return (
      <section className="space-y-4">
        {header}
        {content}
      </section>
    )
  }

  return (
    <Card className="theme-card">
      <CardHeader className="space-y-4">{header}</CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
