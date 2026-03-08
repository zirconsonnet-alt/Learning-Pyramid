from dataclasses import dataclass
from typing import Tuple, TypeAlias

from backend.models.enums import ContentBlockKind
from backend.models.errors import PreconditionFailure
from backend.models.types import MediaAssetId


@dataclass(frozen=True, slots=True)
class ContentBlock:
    kind: ContentBlockKind
    text: str | None = None
    asset_id: MediaAssetId | None = None

    def validate_write_time(self) -> None:
        if self.kind == ContentBlockKind.TEXT:
            if self.text is None or not str(self.text).strip():
                raise PreconditionFailure("ContentBlock(TEXT).text must be non-empty")
            return
        if self.kind == ContentBlockKind.IMAGE:
            if self.asset_id is None or not str(self.asset_id).strip():
                raise PreconditionFailure("ContentBlock(IMAGE).asset_id must be non-empty")
            return
        raise PreconditionFailure(f"Unknown ContentBlockKind: {self.kind}")


RichContent: TypeAlias = Tuple[ContentBlock, ...]


def validate_rich_content_write_time(content: RichContent) -> None:
    if content is None or len(content) == 0:
        raise PreconditionFailure("RichContent must be non-empty")
    for b in content:
        if b is None:
            raise PreconditionFailure("RichContent contains null ContentBlock")
        b.validate_write_time()


def rich_text(text: str) -> RichContent:
    """
    Helper to create a RichContent with a single TEXT block.
    """
    return (ContentBlock(kind=ContentBlockKind.TEXT, text=text),)

