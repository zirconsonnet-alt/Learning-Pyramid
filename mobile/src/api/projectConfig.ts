import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const ProjectTypeSchema = z.enum(["COURSE", "BOOK", "LOOSE_POINTS"])
export type ProjectType = z.infer<typeof ProjectTypeSchema>

const ReviewChainTemplateItemSchema = z.object({
  kind: z.enum(["CONVERGENCE", "REVIEW_TASK"]),
  count: z.number().int().optional(),
})

const LayerConfigSchema = z.object({
  reviewChainTemplate: z.array(ReviewChainTemplateItemSchema),
  aggregationKNode: z.number().int(),
  aggregationKPoint: z.number().int(),
  thresholdRollUpEnabled: z.boolean().default(true),
})

const RollUpStrategySchema = z.enum(["MANUAL", "THRESHOLD_AUTO", "LEARNING_OBJECT_ISOMORPHIC"])
export type RollUpStrategy = z.infer<typeof RollUpStrategySchema>

export const ProjectConfigSchema = z.object({
  projectId: z.string(),
  projectType: ProjectTypeSchema,
  rollUpStrategy: RollUpStrategySchema.default("LEARNING_OBJECT_ISOMORPHIC"),
  updatedAt: z.string(),
  layerConfigs: z.record(z.string(), LayerConfigSchema),
  pushConfig: z
    .object({
      minRecallPointsToEnable: z.number().int(),
      maxHistoryLen: z.number().int(),
      recommendedBatchSize: z.number().int(),
      forgettingCurveDecayPerDay: z.number(),
    })
    .nullable()
    .optional(),
})

export type ProjectConfig = z.infer<typeof ProjectConfigSchema>

export function projectTypeRequiresLearningObjectTree(projectType: ProjectType) {
  return projectType === "COURSE" || projectType === "BOOK"
}

export function projectTypeRequiresAnchor(projectType: ProjectType) {
  return projectType === "COURSE" || projectType === "BOOK"
}

export function projectTypeUsesResolvableCourseAnchor(projectType: ProjectType) {
  return projectType === "COURSE"
}

export function createProjectConfigApi(requester: ApiRequester) {
  return {
    getProjectConfig: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/project-config"),
        responseSchema: ProjectConfigSchema,
      }),
    setLayerConfig: (
      scope: ScopedProjectRef,
      layerIndex: number,
      input: { thresholdRollUpEnabled?: boolean },
    ) =>
      requester.request({
        path: projectApiPath(scope, `/layers/${layerIndex}/config`),
        method: "POST",
        body:
          input.thresholdRollUpEnabled === undefined
            ? {}
            : { thresholdRollUpEnabled: input.thresholdRollUpEnabled },
        responseSchema: z.null(),
      }),
  }
}
