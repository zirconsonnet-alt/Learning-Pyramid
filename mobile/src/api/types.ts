import { createAuthApi } from "./auth"
import { createBaiduNetdiskApi } from "./baiduNetdisk"
import { createCloudAccountsApi } from "./cloudAccounts"
import { createLayersApi } from "./layers"
import { createLearningObjectsApi } from "./learningObjects"
import { createLearningTaskNodesApi } from "./learningTaskNodes"
import { createLearningTasksApi } from "./learningTasks"
import { createMediaApi } from "./media"
import { createProfileApi } from "./profile"
import { createProjectConfigApi } from "./projectConfig"
import { createReviewApi } from "./review"
import { createSubjectsApi } from "./subjects"
import { createSubtitlesApi } from "./subtitles"
import { createSystemApi } from "./system"
import type { ApiRequester } from "./requester"

export type { ApiRequester, ApiRequestOptions, ScopedProjectRef } from "./requester"
export { projectApiPath } from "./requester"

export function createLearningPyramidApi(requester: ApiRequester) {
  return {
    auth: createAuthApi(requester),
    baiduNetdisk: createBaiduNetdiskApi(requester),
    cloudAccounts: createCloudAccountsApi(requester),
    subjects: createSubjectsApi(requester),
    learningObjects: createLearningObjectsApi(requester),
    learningTaskNodes: createLearningTaskNodesApi(requester),
    learningTasks: createLearningTasksApi(requester),
    layers: createLayersApi(requester),
    media: createMediaApi(requester),
    profile: createProfileApi(requester),
    projectConfig: createProjectConfigApi(requester),
    review: createReviewApi(requester),
    subtitles: createSubtitlesApi(requester),
    system: createSystemApi(requester),
  }
}
