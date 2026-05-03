# Quickstart: Live Guide Demos

## Goal

Verify that the in-product guide can render live, controlled product scenes from the existing user manual without relying on static screenshots or real user data.

## Author A Guide Demo Block

Add a standalone block to `docs/learningpyramid-user-manual.md`:

```markdown
:::guide-demo scene="project-directory" state="unbound" highlight="authorize-button" title="绑定本地素材目录"
这个场景展示进入项目设置后，用户应该找到的目录授权入口。
:::
```

## Add Or Update A Scene

1. Add or update the scene renderer under `frontend/src/views/guide/demos/`.
2. Register the scene identifier, supported states, and supported highlights in the guide scene registry.
3. Keep fixtures deterministic and free of real personal data, private learning content, account data, and real local file paths.
4. Confirm the scene can render without a real project, login-only private data, local directory permission, or network request.

## Fixture Privacy Rules

- Use invented names such as sample course, sample project, or demo directory labels.
- Do not include real absolute paths, account identifiers, private learning notes, tokens, secrets, phone numbers, or production content.
- Keep all sample values in `frontend/src/views/guide/demos/guideSceneFixtures.ts` so reviewers can audit them in one place.
- A scene must remain readable when the optional highlight is removed.

## Release Review

1. Open each manual section that contains a `guide-demo` block.
2. Confirm the scene title and caption explain which written step the scene supports.
3. Confirm the visible labels in the scene still match the adjacent guide text.
4. Confirm unsupported scene, state, or highlight references show a contained fallback rather than breaking the page.
5. Record follow-up work here when a scene is too dense or needs a new state before release.

## Run Validation

From the repository root:

```powershell
pnpm -C frontend build
pnpm -C frontend lint
python -m pytest tests/test_frontend_live_guide_demos.py
```

## Manual Review

1. Start the frontend development server.
2. Open the in-product guide.
3. Review the user manual sections for first-use onboarding.
4. Confirm embedded scenes visually match the adjacent written instructions.
5. Confirm narrow and wide layouts keep the guide readable.
6. Confirm unknown scene or state references show a fallback instead of breaking the page.

## Completion Criteria

- At least three onboarding or learning workflows from the manual have live guide scenes.
- Existing text, headings, lists, math, code blocks, links, and navigation still render correctly.
- Every scene uses fixed, privacy-safe fixture data.
- Build, lint, and targeted guide demo tests pass or any unrun check is explicitly documented.
