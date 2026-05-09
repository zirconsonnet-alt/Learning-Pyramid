import re
from functools import total_ordering


_VERSION_RE = re.compile(
    r"^\s*(\d+)\.(\d+)\.(\d+)(?:[-.]?(alpha|beta|rc)(?:[.-]?(\d+))?)?\s*$",
    re.IGNORECASE,
)
_PRERELEASE_RANK = {
    "alpha": 0,
    "beta": 1,
    "rc": 2,
}


@total_ordering
class ComparableVersion:
    def __init__(self, raw: str) -> None:
        match = _VERSION_RE.match(str(raw or ""))
        if match is None:
            raise ValueError(f"invalid version: {raw}")
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease_tag = (match.group(4) or "").lower()
        prerelease_num = int(match.group(5) or 0)
        is_final = 1 if not prerelease_tag else 0
        prerelease_rank = _PRERELEASE_RANK.get(prerelease_tag, -1)
        self.raw = str(raw).strip()
        self._key = (major, minor, patch, is_final, prerelease_rank, prerelease_num)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ComparableVersion):
            return NotImplemented
        return self._key == other._key

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ComparableVersion):
            return NotImplemented
        return self._key < other._key


def compare_versions(left: str, right: str) -> int:
    left_version = ComparableVersion(left)
    right_version = ComparableVersion(right)
    if left_version < right_version:
        return -1
    if left_version > right_version:
        return 1
    return 0
