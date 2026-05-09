import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUBTITLE_EXTENSIONS: tuple[str, ...] = (".srt", ".vtt", ".ass", ".ssa")

_HTML_BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"</?[^>]+>")
_ASS_OVERRIDE_TAG_PATTERN = re.compile(r"\{[^}]*\}")


@dataclass(frozen=True, slots=True)
class SubtitleSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class SubtitleDocument:
    format: str
    segments: tuple[SubtitleSegment, ...]


def find_sibling_subtitle_file(material_path: Path) -> Path | None:
    if not material_path.name:
        return None
    parent = material_path.parent
    if not parent.exists() or not parent.is_dir():
        return None

    stem = material_path.stem.casefold()
    preferred_by_ext = {ext: index for index, ext in enumerate(SUPPORTED_SUBTITLE_EXTENSIONS)}
    best_match: tuple[int, Path] | None = None

    for child in parent.iterdir():
        if not child.is_file():
            continue
        ext = child.suffix.lower()
        preference = preferred_by_ext.get(ext)
        if preference is None:
            continue
        if child.stem.casefold() != stem:
            continue
        if best_match is None or preference < best_match[0]:
            best_match = (preference, child)

    return None if best_match is None else best_match[1]


def parse_subtitle_file(file_path: Path) -> SubtitleDocument:
    ext = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8-sig")
    return parse_subtitle_text(text, suffix=ext)


def parse_subtitle_text(text: str, *, suffix: str) -> SubtitleDocument:
    ext = str(suffix or "").lower()
    if ext == ".srt":
        return SubtitleDocument(format="srt", segments=_parse_srt(text))
    if ext == ".vtt":
        return SubtitleDocument(format="vtt", segments=_parse_vtt(text))
    if ext == ".ass":
        return SubtitleDocument(format="ass", segments=_parse_ass_like(text))
    if ext == ".ssa":
        return SubtitleDocument(format="ssa", segments=_parse_ass_like(text))
    raise ValueError(f"unsupported subtitle extension: {file_path.suffix}")


def _normalize_subtitle_text(text: str) -> str:
    normalized = str(text or "").replace("\ufeff", "").replace("\r", "")
    normalized = normalized.replace("\\N", "\n").replace("\\n", "\n")
    normalized = _HTML_BREAK_PATTERN.sub("\n", normalized)
    normalized = _ASS_OVERRIDE_TAG_PATTERN.sub("", normalized)
    normalized = _HTML_TAG_PATTERN.sub("", normalized)
    lines = [re.sub(r"\s+", " ", line).strip() for line in normalized.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _normalize_segments(items: list[SubtitleSegment]) -> tuple[SubtitleSegment, ...]:
    cleaned = [
        SubtitleSegment(
            start_ms=max(0, int(item.start_ms)),
            end_ms=max(0, int(item.end_ms)),
            text=_normalize_subtitle_text(item.text),
        )
        for item in items
    ]
    cleaned = [item for item in cleaned if item.end_ms > item.start_ms and item.text]
    cleaned.sort(key=lambda item: (item.start_ms, item.end_ms, item.text))
    return tuple(cleaned)


def _parse_srt(text: str) -> tuple[SubtitleSegment, ...]:
    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    for raw_block in blocks:
        lines = [line.strip("\ufeff") for line in raw_block.split("\n") if line.strip()]
        if not lines:
            continue
        timeline_index = 0
        if "-->" not in lines[0] and len(lines) >= 2 and "-->" in lines[1]:
            timeline_index = 1
        if timeline_index >= len(lines) or "-->" not in lines[timeline_index]:
            continue
        start_ms, end_ms = _parse_arrow_timeline(lines[timeline_index], allow_short_hours=False)
        body = "\n".join(lines[timeline_index + 1 :]).strip()
        if body:
            segments.append(SubtitleSegment(start_ms=start_ms, end_ms=end_ms, text=body))
    return _normalize_segments(segments)


def _parse_vtt(text: str) -> tuple[SubtitleSegment, ...]:
    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    for raw_block in blocks:
        lines = [line.strip("\ufeff") for line in raw_block.split("\n")]
        lines = [line for line in lines if line.strip()]
        if not lines:
            continue
        header = lines[0].strip().upper()
        if header == "WEBVTT" or header.startswith("NOTE") or header.startswith("STYLE") or header.startswith("REGION"):
            continue
        timeline_index = 0
        if "-->" not in lines[0] and len(lines) >= 2 and "-->" in lines[1]:
            timeline_index = 1
        if timeline_index >= len(lines) or "-->" not in lines[timeline_index]:
            continue
        start_ms, end_ms = _parse_arrow_timeline(lines[timeline_index], allow_short_hours=True)
        body = "\n".join(lines[timeline_index + 1 :]).strip()
        if body:
            segments.append(SubtitleSegment(start_ms=start_ms, end_ms=end_ms, text=body))
    return _normalize_segments(segments)


def _parse_ass_like(text: str) -> tuple[SubtitleSegment, ...]:
    segments: list[SubtitleSegment] = []
    in_events = False
    fields: list[str] = []

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_events = line.casefold() == "[events]"
            continue
        if not in_events:
            continue
        if line.casefold().startswith("format:"):
            fields = [item.strip().casefold() for item in line.split(":", 1)[1].split(",")]
            continue
        if not line.casefold().startswith("dialogue:") or not fields:
            continue
        payload = line.split(":", 1)[1].lstrip()
        parts = payload.split(",", len(fields) - 1)
        if len(parts) < len(fields):
            continue
        mapped = {field: parts[index].strip() for index, field in enumerate(fields)}
        start_raw = mapped.get("start")
        end_raw = mapped.get("end")
        text_raw = mapped.get("text")
        if not start_raw or not end_raw or not text_raw:
            continue
        start_ms = _parse_ass_timestamp(start_raw)
        end_ms = _parse_ass_timestamp(end_raw)
        segments.append(SubtitleSegment(start_ms=start_ms, end_ms=end_ms, text=text_raw))

    return _normalize_segments(segments)


def _parse_arrow_timeline(line: str, *, allow_short_hours: bool) -> tuple[int, int]:
    left, right = line.split("-->", 1)
    start_ms = _parse_web_timestamp(left.strip().split(" ", 1)[0], allow_short_hours=allow_short_hours)
    end_ms = _parse_web_timestamp(right.strip().split(" ", 1)[0], allow_short_hours=allow_short_hours)
    return start_ms, end_ms


def _parse_web_timestamp(raw: str, *, allow_short_hours: bool) -> int:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("empty subtitle timestamp")
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours_text, minutes_text, seconds_text = parts
    elif len(parts) == 2 and allow_short_hours:
        hours_text, minutes_text, seconds_text = "0", parts[0], parts[1]
    else:
        raise ValueError(f"invalid subtitle timestamp: {raw}")
    seconds_parts = seconds_text.split(".", 1)
    seconds = int(seconds_parts[0])
    millis_text = seconds_parts[1] if len(seconds_parts) > 1 else "0"
    millis = int((millis_text + "000")[:3])
    return ((int(hours_text) * 60 + int(minutes_text)) * 60 + seconds) * 1000 + millis


def _parse_ass_timestamp(raw: str) -> int:
    value = str(raw or "").strip()
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid ASS subtitle timestamp: {raw}")
    hours = int(parts[0])
    minutes = int(parts[1])
    second_parts = parts[2].split(".", 1)
    seconds = int(second_parts[0])
    centis = int((second_parts[1] if len(second_parts) > 1 else "0")[:2].ljust(2, "0"))
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + centis * 10
