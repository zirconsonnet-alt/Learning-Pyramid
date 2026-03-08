from backend.models.types import ReviewTaskQueueId

# 3.4.2 / 4.1.2：系统常量（全局队列 ID）
GLOBAL_QUEUE: ReviewTaskQueueId = ReviewTaskQueueId("GLOBAL_QUEUE")

# 1.8：材料白名单单例 ID（项目内固定常量，避免多实例分叉）
MATERIAL_ALLOWLIST_V1: str = "MATERIAL_ALLOWLIST_V1"
