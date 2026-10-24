---
name: sync-docs
description: >-
  Check whether README.md, HARDENING.md, AGENTS.md and the header
  comment/docstring of each changed script (ci/*.sh, ci/*.py,
  shared/**/*.sh, .github/workflows/*.yml) still accurately describe
  current behavior after a code change, and fix any drift found.
  Invoke proactively before committing a change that touches the
  pipeline (.github/, images.yaml, ci/), a shared build input
  (shared/), or an image's hardening posture (Dockerfiles,
  .trivyignore), or whenever explicitly asked to update docs for a
  recent change. Do not invoke for changes with no doc surface (pure
  test files).
---

# sync-docs

Every script and workflow opens with a short header explaining its
flow, the env it consumes and the non-obvious "why" of its design;
README.md mirrors the pipeline, the versioning and the catalog, and
HARDENING.md mirrors what the Dockerfiles lift or accept. All of them
drift easily — this skill is the review pass that catches it.

## Procedure

1. **Scope the diff.** `git diff` (uncommitted) or `git show`/`git diff
   HEAD~1` (committed). Look at `.github/`, `images.yaml`, `ci/`,
   `shared/`, `*/manifest.yaml`, `*/Dockerfile`, `*/.trivyignore`,
   `apps/*/rootfs/**`.

2. **For each changed script/workflow**, re-read its header or the
   workflow's top comment and check it against the new code:
   - flow (step order/count), env vars, inputs and args it claims to read;
   - tools/images/registries/tags/paths it names;
   - stated rationale — is the constraint still true?
   - cross-references to other files/jobs/actions by name.

3. **For each changed subsystem**, grep README.md, HARDENING.md and
   AGENTS.md for the related keywords (job names, action names, make
   targets, env vars, tags, paths) and check those sections the same
   way. A change to a `-dev` variant, a browser flag or a
   `.trivyignore` almost always touches HARDENING.md; a change to the
   toolkit consumption (`@main`, `WAAS_CORE_IMAGES_DIR`) touches
   README, AGENTS and CONTRIBUTING.

4. **Fix only the drift you found.** Terse comments that explain the
   why; no comment where nothing non-obvious would be lost; no new
   sections beyond what the diff changed.

5. **Report concisely**: which files got a doc fix and why, and which
   changed files were checked and found accurate.

## When NOT to touch something

- Purely internal changes with no effect on documented behavior.
- Generated files (`github-matrices.json`, `Dockerfile.generated`,
  `catalogs/`).
- `ci/tests/`.
- The core's docs (`CONTRACT.md`, its `HARDENING.md`): a change that
  needs them changes the core repo.
