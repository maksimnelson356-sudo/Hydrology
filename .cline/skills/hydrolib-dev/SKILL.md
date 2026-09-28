---
name: hydrolib-dev
description: >
  Development workflow for HydroSphere/hydrolib Python projects.
  Use for Python code changes, debugging, refactoring, tests, pytest,
  ruff, pyright, Git review, and methodology-sensitive engineering changes.
---

# HydroLib Development Workflow

## Core rule

Before modifying code, inspect the relevant implementation and tests.
Prefer the smallest safe change that preserves the existing public API.

## Python

Use the repository's existing Python environment and project tooling.

Prefer:
- `pytest -q` for tests
- targeted pytest tests first
- `ruff check` for lint
- `pyright` for type checking when relevant

Do not rewrite working code merely to satisfy style preferences.

## Testing

After a code change:
1. Run the narrowest relevant test.
2. If it passes, run the relevant module/test group.
3. For broad changes, run the full suite.

When a test fails:
- identify the actual cause first;
- do not blindly weaken or rewrite the test;
- do not hide errors by changing assertions unless the expected behavior itself changed.

Keep test output concise. Prefer summaries and failing test names over dumping full logs.

## Git

Before significant changes inspect:
- `git status --short`
- `git diff --stat`
- relevant `git diff`

Never run destructive commands such as:
- `git reset --hard`
- `git clean -fd`
- force push

unless the user explicitly requests them.

Preserve unrelated working-tree changes.

## Project safety

Do not modify:
- `.env`
- credentials
- API keys
- generated artifacts

unless explicitly required.

Respect `.gitignore`.

## Engineering methodology

For numerical/hydrological code, preserve formulas, units, validation rules,
and documented methodology unless the task explicitly changes them.

When changing a numerical algorithm:
- explain the affected invariant;
- add or update regression tests;
- test edge cases and boundary conditions.

## Completion

Before claiming completion, report:
- files changed;
- tests run;
- test result;
- remaining uncertainty, if any.
