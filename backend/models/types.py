from datetime import datetime, timezone
import hashlib
from pathlib import PurePosixPath
from typing import Any, NewType, TypeAlias, Union

# =========
# ID types
# =========
ProjectId = NewType("ProjectId", str)
InstanceId = NewType("InstanceId", str)
LearningObjectNodeId = NewType("LearningObjectNodeId", str)
RecallPointId = NewType("RecallPointId", str)
LearningTaskId = NewType("LearningTaskId", str)
LearningTaskNodeId = NewType("LearningTaskNodeId", str)
RangeId = NewType("RangeId", str)

# 这些是后续章节会用到的，这里先占位，避免模型层未来改动大：
ReviewTaskId = NewType("ReviewTaskId", str)
ReviewChainId = NewType("ReviewChainId", str)
ReviewTaskQueueId = NewType("ReviewTaskQueueId", str)
LayerId = NewType("LayerId", str)
DimensionId = NewType("DimensionId", str)
JudgementOptionId = NewType("JudgementOptionId", str)
AggregationEventId = NewType("AggregationEventId", str)
ConvergenceId = NewType("ConvergenceId", str)
ConvergenceRuleId = NewType("ConvergenceRuleId", str)
MediaAssetId = NewType("MediaAssetId", str)
AsrArtifactId = NewType("AsrArtifactId", str)
TempContextFragmentId = NewType("TempContextFragmentId", str)
QASessionId = NewType("QASessionId", str)
CandidateRecallPointId = NewType("CandidateRecallPointId", str)
MemoryCanvasId = NewType("MemoryCanvasId", str)
MemoryCanvasVersionId = NewType("MemoryCanvasVersionId", str)
CanvasEdgeId = NewType("CanvasEdgeId", str)
StoryArtifactId = NewType("StoryArtifactId", str)

# =========
# Scalar types
# =========
# PurePath：按规格 1.1.1，必须以 POSIX 语义 PurePosixPath 作为唯一规范化实现
PurePath: TypeAlias = PurePosixPath

# Timestamp：对外语义为 UTC 时间点；最小精度 ms（对外解释按 ms）
Timestamp: TypeAlias = datetime

# LabelVector：这里用 tuple[int,...] 表达（值域约束在上层或 validator）
LabelVector: TypeAlias = tuple[int, ...]


# =========================
# Canonical text / ordering
# =========================
def id_canonical_text(x: Any) -> str:
    """
    0a.9 强约束：跨平台一致、与 locale 无关的确定性映射。
    这里的实现假设所有 xxxId 底层为 str / NewType(str)。
    """
    if x is None:
        raise ValueError("id_canonical_text(None) is invalid")
    # NewType 在运行时就是底层类型（str），但保守起见强转
    return str(x)


def now_utc_ms() -> Timestamp:
    """
    0a.10：系统时钟生成，UTC 语义；对外可观察按毫秒解释。
    为避免对外暴露微秒级差异，这里直接截断到毫秒精度（不做四舍五入）。
    """
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def normalize_material_id_to_purepath(material_id: Union[str, PurePath]) -> PurePath:
    """
    1.1.1：若 material_id 输入为 str：
    - 先把 '\\' 替换成 '/'
    - 再用 PurePosixPath 构造
    禁止在写入期做可达性探测或外部访问。
    """
    if isinstance(material_id, PurePosixPath):
        return material_id
    if not isinstance(material_id, str):
        raise TypeError(f"material_id must be str|PurePosixPath, got {type(material_id)}")
    normalized = material_id.replace("\\", "/")
    return PurePosixPath(normalized)


def material_display_name(material_id: PurePath) -> str:
    """
    1.1.1 派生字段：能解释为路径则取文件名，否则回退 as_posix。
    PurePosixPath 总能给 name；空路径 name 可能是 ''。
    """
    name = material_id.name
    return name if name else material_id.as_posix()


# =========================
# Stable IDs from rel_path (0b.1.5b)
# =========================
def fs_hash32(rel_path: PurePath) -> str:
    """
    0b.1.5b 强约束：基于 rel_path.as_posix() 的 SHA-256 hexdigest 截断 32 位（小写十六进制）。
    """
    return hashlib.sha256(rel_path.as_posix().encode("utf-8")).hexdigest()[:32]


def id_from_rel_path(rel_path: PurePath) -> InstanceId:
    """
    0b.1.5b：InstanceId('instfs_' + fs_hash32(rel_path))
    """
    return InstanceId(f"instfs_{fs_hash32(rel_path)}")


def node_id_from_rel_path(rel_path: PurePath, kind: str) -> LearningObjectNodeId:
    """
    0b.1.5b：LearningObjectNodeId('lonfs_{leaf|dir}_' + fs_hash32(rel_path))

    kind ∈ {'LEAF', 'DIR'}.
    """
    if kind == "LEAF":
        prefix = "lonfs_leaf"
    elif kind == "DIR":
        prefix = "lonfs_dir"
    else:
        raise ValueError("kind must be 'LEAF' or 'DIR'")
    return LearningObjectNodeId(f"{prefix}_{fs_hash32(rel_path)}")
