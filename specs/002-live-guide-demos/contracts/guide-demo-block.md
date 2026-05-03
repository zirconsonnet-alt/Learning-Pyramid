# Contract: Guide Demo Markdown Block

## Purpose

Allow guide authors to embed controlled live product scenes in plain Markdown without static screenshots.

## Block Syntax

```markdown
:::guide-demo scene="project-directory" state="unbound" highlight="authorize-button" title="绑定本地素材目录"
可选说明文字。
:::
```

## Required Attributes

- `scene`: Stable guide scene identifier.
- `state`: Stable example state for the selected scene.

## Optional Attributes

- `highlight`: Stable target inside the selected scene.
- `title`: Reader-facing title shown above the scene.

## Optional Body

The body between the opening and closing directives is treated as a plain caption. It may be omitted.

## Parsing Rules

- Opening directive must start at the beginning of a line with `:::guide-demo`.
- Closing directive must be a standalone `:::` line.
- Attribute values must be quoted.
- Unknown attributes are ignored for forward compatibility.
- Invalid or incomplete directives render as a fallback guide block, not as raw broken markup.
- Directives inside code fences are treated as code, not live scenes.

## Rendering Rules

- The guide renderer resolves `scene` and `state` through the scene registry.
- If `highlight` is unsupported by the scene, the scene still renders without the highlight and exposes a non-blocking fallback note for maintainers.
- If `scene` or `state` is unknown, the guide renders a reader-friendly fallback block.
- Scenes are visually contained in the guide content column and must not require interaction to understand the documented step.

## Privacy And Safety Rules

- Guide demo blocks must not include real user names, private learning content, account data, tokens, or real local file paths.
- Guide demo rendering must not trigger writes, imports, purchases, permission prompts, or network requests.
