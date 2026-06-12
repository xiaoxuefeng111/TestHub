# Agent Teams for Tongdaxin Testing Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a runnable Agent Teams setup for the current Tongdaxin Testing Platform repository, then kick off Team Lead to coordinate environment, backend, frontend, database, and testing work.

**Architecture:** Use a `supervisor` session as the Team Lead entrypoint because the current platform exposes session and team-attachment primitives but not a standalone `create_team` API. After the Team Lead is created, verify whether a `teamId` exists; if it does, create and attach fixed specialist sessions. If not, continue with Team Lead plus dynamic child-agent dispatch.

**Tech Stack:** SpectrAI built-in session tools, Agent Teams context attachment, Django, Vue/Vite, MySQL, repository docs under `docs/plans/`.

---

### Task 1: Persist team design artifacts

**Files:**
- Create: `docs/plans/2026-06-08-agent-teams-testhub-design.md`
- Create: `docs/plans/2026-06-08-agent-teams-testhub-implementation.md`

**Step 1: Verify the plans directory exists**

Run: `rg --files docs`
Expected: output includes `docs/plans/...`

**Step 2: Save the validated design document**

Action: write the team design to `docs/plans/2026-06-08-agent-teams-testhub-design.md`
Expected: file exists with team roles, prompts, execution flow, and success criteria.

**Step 3: Save this implementation plan**

Action: write the plan to `docs/plans/2026-06-08-agent-teams-testhub-implementation.md`
Expected: file exists with executable session-creation steps.

**Step 4: Avoid auto-commit because worktree is already dirty**

Run: `git status --short`
Expected: many existing modified files unrelated to this plan.

### Task 2: Capture current session context for session inheritance

**Files:**
- Read-only context, no repository file changes

**Step 1: Read current session context**

Action: call `get_current_session_context`
Expected: return includes current `providerId`, `mode`, and `sessionId`.

**Step 2: Record required creation parameters**

Capture:
- `cwd = g:\Working\AI_Work\testhub_platform`
- `providerId = current session providerId`
- `inheritFromParentSession = current sessionId`

**Step 3: Decide Team Lead session mode**

Decision: use `mode = supervisor`
Expected: created session can coordinate and dispatch work.

### Task 3: Create Team Lead session

**Files:**
- Read-only context, no repository file changes

**Step 1: Create the Team Lead session**

Action: call `create_standalone_session` with:
- `mode = supervisor`
- `name = Tongdaxin Team Lead`
- `cwd = g:\Working\AI_Work\testhub_platform`
- `providerId = <current providerId>`
- `inheritFromParentSession = <current sessionId>`
- `goalAnchor = Deliver a runnable Tongdaxin Testing Platform project with environment, backend, frontend, database, testing, and README completion`
- `initialPromptVisibility = visible`
- `initialPrompt =` a detailed prompt instructing the Team Lead to split work into environment, backend, frontend, database, and testing streams and begin execution immediately.

**Step 2: Verify session creation succeeded**

Expected: tool returns a new `sessionId`.

**Step 3: Read the new Team Lead context**

Action: call `get_current_session_context` with the new `sessionId`
Expected: context shows `mode = supervisor`; note whether `teamId` is null or non-null.

### Task 4: Decide fixed-team attachment strategy

**Files:**
- Read-only context, no repository file changes

**Step 1: Branch on `teamId` presence**

If `teamId` exists:
- continue to Task 5 and create fixed specialist sessions attached to that `teamId`

If `teamId` is null:
- skip Task 5 creation/attachment
- continue directly to Task 6 and let Team Lead use dynamic child-agent dispatch

**Step 2: Document the chosen branch in the user-facing summary**

Expected: final response clearly states whether the result is a fixed attached team or supervisor-led dynamic team.

### Task 5: Create and attach fixed specialist sessions (conditional)

**Files:**
- Read-only context, no repository file changes

**Step 1: Create Environment session**

Action: create a standalone session for environment setup work using the same `cwd` and `providerId`, then attach it with role name `环境配置 Agent`.

**Step 2: Create Backend session**

Action: create a standalone session focused on Django backend fixes, then attach it with role name `后端服务 Agent`.

**Step 3: Create Frontend session**

Action: create a standalone session focused on Vue/Vite frontend fixes, then attach it with role name `前端开发 Agent`.

**Step 4: Create Database session**

Action: create a standalone session focused on MySQL initialization and connectivity, then attach it with role name `数据库 Agent`.

**Step 5: Create Testing session**

Action: create a standalone session focused on smoke testing and defect feedback, then attach it with role name `测试验证 Agent`.

**Step 6: Verify each attachment**

Action: call `attach_session_to_team` for each specialist session
Expected: all sessions are linked to the same `teamId` with the correct `roleName`.

### Task 6: Kick off execution

**Files:**
- Read-only context, no repository file changes at this step

**Step 1: Send the kickoff brief through the Team Lead initial prompt**

Expected: Team Lead immediately starts repository scan and work decomposition.

**Step 2: Ensure the kickoff prompt includes these constraints**

- Split work into environment / backend / frontend / database / testing
- Coordinate cross-module conflicts first
- Prefer minimal safe changes
- Update README only after the run path is validated
- Produce a final runnable state and summary

**Step 3: Do not claim success prematurely**

Expected: only report “team created and started” at this stage, not “project fully fixed”.

### Task 7: Report results back to the user

**Files:**
- No repository file changes required

**Step 1: Provide created session IDs**

Include:
- Team Lead session ID
- Specialist session IDs if fixed-team branch was available

**Step 2: Provide the saved document paths**

Include:
- `docs/plans/2026-06-08-agent-teams-testhub-design.md`
- `docs/plans/2026-06-08-agent-teams-testhub-implementation.md`

**Step 3: State the next execution mode**

Report one of:
- `fixed attached team is running`
- `supervisor-led dynamic team is running`

**Step 4: Defer Git commit**

Explain that auto-commit was intentionally skipped because the working tree already contained many unrelated changes.
