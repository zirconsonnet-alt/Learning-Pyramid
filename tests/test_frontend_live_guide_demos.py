from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE_PAGE = ROOT / "frontend/src/views/guide/GuidePage.tsx"
DEMO_DIR = ROOT / "frontend/src/views/guide/demos"
REGISTRY = DEMO_DIR / "guideSceneRegistry.tsx"
FIXTURES = DEMO_DIR / "guideSceneFixtures.ts"
MANUAL = ROOT / "docs/learningpyramid-user-manual.md"
QUICKSTART = ROOT / "specs/002-live-guide-demos/quickstart.md"


ATTR_RE = re.compile(r'([a-zA-Z][\w-]*)="([^"]*)"')
OPENING_RE = re.compile(r"^:::guide-demo\b(?P<attrs>.*)$")
TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PRIVATE_VALUE_RE = re.compile(
    r"(?:[A-Za-z]:\\|/Users/|/home/|token|secret|password|bylou|真实|私人|身份证|手机号)",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_guide_demo_blocks(markdown: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    in_fence = False
    lines = markdown.replace("\r\n", "\n").split("\n")
    index = 0

    while index < len(lines):
      line = lines[index]
      stripped = line.strip()
      if re.match(r"^(```|~~~)", stripped):
          in_fence = not in_fence
          index += 1
          continue

      if in_fence:
          index += 1
          continue

      opening = OPENING_RE.match(line)
      if not opening:
          index += 1
          continue

      attrs = dict(ATTR_RE.findall(opening.group("attrs")))
      caption_lines: list[str] = []
      index += 1
      while index < len(lines) and lines[index].strip() != ":::":
          caption_lines.append(lines[index])
          index += 1

      attrs["caption"] = "\n".join(caption_lines).strip()
      blocks.append(attrs)
      if index < len(lines):
          index += 1

    return blocks


def _registry_entries() -> dict[str, dict[str, set[str] | str]]:
    source = _read(REGISTRY)
    entries: dict[str, dict[str, set[str] | str]] = {}
    bodies = re.split(r"\n\s*\},\n\s*\{\n\s*scene:", source)
    for index, raw_body in enumerate(bodies):
        body = raw_body if index == 0 else '{\n    scene:' + raw_body
        if "scene:" not in body or "states:" not in body:
            continue
        scene_match = re.search(r'scene:\s*"([^"]+)"', body)
        if not scene_match:
            continue
        scene = scene_match.group(1)
        states = set(re.findall(r'\{\s*state:\s*"([^"]+)"', body))
        highlights_match = re.search(r"highlights:\s*\[([^\]]*)\]", body, re.DOTALL)
        highlights = set(re.findall(r'"([^"]+)"', highlights_match.group(1) if highlights_match else ""))
        label = re.search(r'label:\s*"([^"]+)"', body)
        description = re.search(r'description:\s*"([^"]+)"', body)
        entries[scene] = {
            "states": states,
            "highlights": highlights,
            "label": label.group(1) if label else "",
            "description": description.group(1) if description else "",
        }
    return entries


def test_parser_contract_is_implemented_for_demo_blocks() -> None:
    source = _read(GUIDE_PAGE)

    assert 'type: "guideDemo"' in source
    assert "parseGuideDemoOpening" in source
    assert "parseGuideDemoAttributes" in source
    assert "invalid-directive" in source
    assert "guideSceneRegistry" in source
    assert "GuideDemoFrame" in source


def test_parser_contract_covers_quoted_attributes_caption_and_code_fences() -> None:
    sample = '''
Intro text.

:::guide-demo scene="project-directory" state="unbound" highlight="authorize-button" title="绑定本地素材目录"
这个场景展示目录授权入口。
:::

```markdown
:::guide-demo scene="inside-code" state="ignored"
:::
```

:::guide-demo scene=broken state="missing-quotes"
:::
'''

    blocks = _parse_guide_demo_blocks(sample)

    assert blocks == [
        {
            "scene": "project-directory",
            "state": "unbound",
            "highlight": "authorize-button",
            "title": "绑定本地素材目录",
            "caption": "这个场景展示目录授权入口。",
        },
        {
            "state": "missing-quotes",
            "caption": "",
        },
    ]


def test_manual_has_three_onboarding_demo_blocks_with_valid_tokens() -> None:
    blocks = _parse_guide_demo_blocks(_read(MANUAL))

    assert len(blocks) >= 3
    for block in blocks:
        assert TOKEN_RE.match(block.get("scene", ""))
        assert TOKEN_RE.match(block.get("state", ""))
        if block.get("highlight"):
            assert TOKEN_RE.match(block["highlight"])
        assert block.get("title")
        assert block.get("caption")


def test_manual_demo_references_are_covered_by_registry() -> None:
    entries = _registry_entries()

    for block in _parse_guide_demo_blocks(_read(MANUAL)):
        scene = block["scene"]
        assert scene in entries
        assert block["state"] in entries[scene]["states"]
        if block.get("highlight"):
            assert block["highlight"] in entries[scene]["highlights"]


def test_registry_supports_fallbacks_and_validation_helpers() -> None:
    source = _read(REGISTRY)
    frame_source = _read(DEMO_DIR / "GuideDemoFrame.tsx")

    assert "resolveGuideScene" in source
    assert "validateGuideSceneReference" in source
    assert "unsupported-highlight" in source
    assert "unknown-scene" in source
    assert "unsupported-state" in source
    assert "maintainerHint" in frame_source


def test_registry_metadata_is_complete_for_review() -> None:
    entries = _registry_entries()

    assert len(entries) >= 3
    for scene, entry in entries.items():
        assert entry["label"], scene
        assert entry["description"], scene
        assert entry["states"], scene

    registry_source = _read(REGISTRY)
    assert registry_source.count("stateDescription") >= 3


def test_fixtures_are_deterministic_and_privacy_safe() -> None:
    source = _read(FIXTURES)

    assert "GUIDE_SCENE_FIXTURES" in source
    assert "sampleDirectoryLabel" in source
    assert "示例课程素材" in source
    assert not PRIVATE_VALUE_RE.search(source)
    assert "I:\\" not in source
    assert "C:\\" not in source


def test_quickstart_documents_authoring_privacy_and_review() -> None:
    source = _read(QUICKSTART)

    assert "Author A Guide Demo Block" in source
    assert "fixture privacy" in source.lower() or "隐私" in source
    assert "Release Review" in source or "发布" in source
