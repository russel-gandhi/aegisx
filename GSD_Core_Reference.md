# GSD Core — Complete Reference

> **Git. Ship. Done.** A meta-prompting, context-engineering, and spec-driven development system for AI coding agents.
> Source: https://github.com/open-gsd/gsd-core (branch: `next`)

---

## Does GSD work with Claude?

**Yes — Claude Code is the primary target runtime.** The repo explicitly names Claude Code first in every list, ships a `.claude-plugin/` directory, and its own README closes with: *"Claude Code is powerful. GSD Core makes it reliable."*

The installer (`npx @opengsd/gsd-core@latest`) asks which runtime you're using; select `claude`. GSD installs slash commands into `~/.claude/` and sets up hooks, agents, and skills for Claude Code specifically.

> Note: GSD **does not** work in the Claude.ai chat interface (claude.ai). It is designed for **Claude Code** (the CLI/agentic coding tool), not the conversational web UI.

---

## Supported Runtimes

`claude` · `antigravity` · `augment` · `cline` · `codebuddy` · `codex` · `copilot` · `cursor` · `gemini` (sunset 2026-06-18, succeeded by Antigravity) · `hermes` · `kilo` · `opencode` · `qwen` · `trae` · `windsurf`

---

## Install

```bash
npx @opengsd/gsd-core@latest
# Prompts: runtime selection + global vs local install
```

**Start a project:**
```bash
/gsd-new-project   # greenfield
/gsd-onboard       # existing codebase
```

---

## Slash Command Syntax

| Runtime | Form |
|---------|------|
| Claude Code / Copilot / OpenCode / Kilo | `/gsd-command-name [args]` (hyphen) |
| Antigravity (formerly Gemini CLI) | `/gsd:command-name [args]` (colon) |
| Codex | `$gsd-command-name [args]` |

The installer writes the correct form for your runtime automatically.

---

## The Phase Loop

Each milestone repeats a 5-step loop, one phase at a time:

1. **Discuss** — capture implementation decisions before planning
2. **Plan** — research, decompose, verify the plan fits a fresh context window
3. **Execute** — run plans in parallel waves; each executor starts with a clean 200k-token context
4. **Verify** — walk through what was built; diagnose and fix before declaring done
5. **Ship** — create the PR, archive the phase, repeat for the next milestone

---

## Why It Works

- **Context rot prevention**: Heavy work runs in fresh-context subagents; the main session stays lean
- **Session continuity**: Structured artifacts (`STATE.md`, `CONTEXT.md`) survive session boundaries
- **Verification before done**: The verify step walks through what was built and generates fix plans before a phase is declared complete

---

## Namespace Meta-Skills (v1.40+)

Six routers keep token cost low (~120 tokens vs ~2,150 for a flat listing):

| Command | Routes to |
|---------|-----------|
| `/gsd-workflow` | Phase pipeline — discuss / plan / execute / verify / phase / progress |
| `/gsd-project` | Project lifecycle — milestones, audits, summary |
| `/gsd-quality` | Quality gates — code review, debug, audit, security, eval, ui |
| `/gsd-context` | Codebase intelligence — map, graphify, docs, learnings |
| `/gsd-manage` | Management — config, workspace, workstreams, thread, update, ship, inbox |
| `/gsd-ideate` | Exploration & capture — explore, sketch, spike, spec, capture |

All concrete commands (e.g. `/gsd-plan-phase`) remain directly invocable.

---

## Command Reference

### Core Workflow

**`/gsd-new-project`** — Initialize project with deep context gathering.
- `--auto @file.md` — Auto-extract from document, skip interactive questions
- Produces: `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `config.json`, `CLAUDE.md`

**`/gsd-discuss-phase [N]`** — Gather phase context through adaptive questioning before planning.
- `--all` · `--auto` · `--batch` · `--analyze` · `--power` · `--assumptions`

**`/gsd-plan-phase [N]`** — Research, plan, and verify a phase.
- `--auto` · `--research` · `--skip-research` · `--research-phase <N>` · `--view` · `--gaps`
- `--skip-verify` · `--prd <file>` · `--ingest <path>` · `--reviews` · `--validate` · `--bounce`
- Produces: `{phase}-RESEARCH.md`, `{phase}-{N}-PLAN.md`, `{phase}-VALIDATION.md`

**`/gsd-execute-phase N`** — Execute all plans with wave-based parallelization.
- `--wave N` · `--validate` · `--cross-ai` · `--no-cross-ai`
- Produces: per-plan `{phase}-{N}-SUMMARY.md`, git commits, `{phase}-VERIFICATION.md`

**`/gsd-verify-work [N]`** — User acceptance testing with auto-diagnosis.
- Produces: `{phase}-UAT.md`, fix plans if issues found

**`/gsd-ship [N]`** — Create PR from completed phase work.
- `--draft` — Create as draft PR

### Navigation

**`/gsd-progress`** — Show status, next steps, auto-advance to next logical workflow step.
- `--next` — Advance automatically
- `--do "task"` — Dispatch freeform intent to best GSD command
- `--forensic` — Standard report + 6-check integrity audit

**`/gsd-resume-work`** — Restore full context from last session.

**`/gsd-pause-work`** — Save context handoff when stopping mid-phase.
- `--report` — Also generate post-session summary

**`/gsd-manager`** — Interactive command center for managing multiple phases.
- Dashboard of all phases with visual status indicators
- Dispatches work: discuss inline, plan/execute as background agents
- `--analyze-deps` — Scan ROADMAP phases for dependency relationships

### Phase Management

**`/gsd-phase [description]`** — CRUD for phases in ROADMAP.md.
- `--insert <N>` · `--remove <N>` · `--edit <N>` · `--force`

**`/gsd-plan-review-convergence N`** — Cross-AI plan convergence loop (plan → review → replan cycles, max 3).
- `--codex` · `--gemini` · `--claude` · `--opencode` · `--all` · `--max-cycles N`

**`/gsd-validate-phase [N]`** — Retroactively audit and fill Nyquist validation gaps.

### Spiking & Sketching

**`/gsd-spike [idea]`** — Run 2–5 focused feasibility experiments.
- `--quick` · `--wrap-up` (package findings into reusable skill)
- Produces: `.planning/spikes/NNN-experiment-name/`

**`/gsd-sketch [idea]`** — Explore design directions via throwaway HTML mockups (2–3 variants).
- `--quick` · `--text` · `--wrap-up`
- Produces: `.planning/sketches/NNN-descriptive-name/index.html`

### Code Quality

**`/gsd-code-review N`** — Review source files changed during a phase.
- `--depth=quick|standard|deep`
- `--files file1,file2,...`
- `--fix` — Auto-fix findings after review
- `--fix --all` — Include Info findings
- `--fix --auto` — Fix + re-review loop (max 3 iterations)

**`/gsd-audit-fix`** — Autonomous audit-to-fix pipeline.
- `--source <audit>` · `--severity high|medium|all` · `--max N` · `--dry-run`

**`/gsd-debug [description]`** — Systematic debugging with persistent state.
- `--diagnose` — Diagnosis-only
- Subcommands: `list` · `status <slug>` · `continue <slug>`

**`/gsd-add-tests [N]`** — Generate tests for a completed phase.

**`/gsd-secure-phase [N]`** — Retroactively verify threat mitigations.
- Produces: `{phase}-SECURITY.md`

### Brownfield & Intelligence

**`/gsd-onboard`** — Onboard an existing codebase into GSD.

**`/gsd-map-codebase [area]`** — Analyze existing codebase with parallel mapper agents.
- `--fast` · `--query <term>` · `--focus tech|arch|quality|concerns|tech+arch`

**`/gsd-graphify`** — Build, query, and inspect the project knowledge graph.
- `build` · `query <term>` · `status` · `diff`
- Requires `graphify.enabled: true` in config

**`/gsd-extract-learnings N`** — Extract reusable patterns from completed phase work.
- `--all` · `--format markdown|json`
- Produces: `.planning/learnings/{phase}-LEARNINGS.md`

### Task Capture & Backlog

**`/gsd-capture [text]`** — Capture ideas, tasks, notes, seeds.
- `--note [text]` · `--backlog <description>` · `--seed [idea]` · `--list` · `--global`

**`/gsd-review-backlog`** — Review and promote backlog items to active milestone.

**`/gsd-thread [name|description]`** — Manage persistent context threads for cross-session work.
- Subcommands: `list` · `list --open` · `list --resolved` · `status <slug>` · `close <slug>`

### Milestone Management

**`/gsd-audit-uat`** — Cross-phase audit of all outstanding UAT items.

**`/gsd-audit-milestone`** — Verify milestone met its definition of done.

**`/gsd-complete-milestone`** — Archive milestone, tag release.

**`/gsd-milestone-summary [version]`** — Generate comprehensive project summary.
- Produces: `.planning/reports/MILESTONE_SUMMARY-v{version}.md`

**`/gsd-new-milestone [name]`** — Start next version cycle.
- `--reset-phase-numbers` — Restart milestone at Phase 1

### Configuration

**`/gsd-settings`** — Interactive configuration (Planning / Execution / Docs / Features / Model / Misc).

**`/gsd-config`** — Configure workflow toggles, advanced knobs, integrations.
- `--advanced` · `--integrations` · `--profile quality|balanced|budget|inherit`

**`/gsd-surface`** — Toggle which skills are surfaced without reinstall.
- `list` · `status` · `profile <name>` · `disable <cluster>` · `enable <cluster>` · `reset`

**`/gsd-update`** — Update GSD with changelog preview.
- `--sync` · `--reapply`

**`/gsd-workspace`** — Manage isolated workspace environments.
- `--new` · `--list` · `--remove <name>` · `--name` · `--repos` · `--strategy worktree|clone`

### Utilities

**`/gsd-quick [task]`** — Execute ad-hoc task with GSD guarantees.
- `--full` · `--validate` · `--discuss` · `--research`
- Subcommands: `list` · `status <slug>` · `resume <slug>`

**`/gsd-fast "task"`** — Execute trivial task inline, no subagents or planning overhead.

**`/gsd-autonomous`** — Run all remaining phases autonomously.
- `--from N` · `--to N` · `--interactive`

**`/gsd-undo`** — Safe git revert with dependency checks.
- `--last N` · `--phase NN` · `--plan NN-MM`

**`/gsd-import`** — Ingest an external plan file into GSD.
- `--from <filepath>` · `--from-gsd2`

**`/gsd-ingest-docs [path]`** — Bootstrap `.planning/` from existing ADRs, PRDs, SPECs.
- `--mode new|merge` · `--manifest <file>` · `--resolve auto`

**`/gsd-health`** — Validate `.planning/` directory integrity.
- `--repair` · `--context`

**`/gsd-cleanup`** — Archive accumulated phase directories from completed milestones.

**`/gsd-forensics [description]`** — Post-mortem investigation for failed GSD workflows.
- Produces: `.planning/forensics/report-{timestamp}.md`

**`/gsd-review --phase N`** — Cross-AI peer review of phase plans.
- `--gemini` · `--claude` · `--codex` · `--opencode` · `--cursor` · `--ollama` · `--all`
- Produces: `{phase}-REVIEWS.md` (consumable by `/gsd-plan-phase --reviews`)

**`/gsd-docs-update`** — Generate or update project documentation.
- `--force` · `--verify-only`

**`/gsd-ui-phase [N]`** — Generate UI design contract for frontend phases.

**`/gsd-ui-review [N]`** — Retroactive 6-pillar visual audit of implemented frontend.

**`/gsd-ai-integration-phase [N]`** — Generate AI-SPEC.md design contract for AI-building phases.

**`/gsd-eval-review [N]`** — Audit an executed AI phase's evaluation coverage.

**`/gsd-stats`** — Display project statistics.

**`/gsd-profile-user`** — Generate developer behavioral profile from session analysis.

**`/gsd-pr-branch [target]`** — Create a clean PR branch filtering out `.planning/` commits.

**`/gsd-explore [topic]`** — Socratic ideation session.

**`/gsd-workstreams`** — Manage parallel workstreams.
- Subcommands: `list` · `create <name>` · `status <name>` · `switch <name>` · `progress` · `complete <name>` · `resume <name>`

**`/gsd-help`** — Show GSD commands.
- `--brief` · `--full` · `<topic>`

---

## Key Artifacts & File Layout

```
.planning/
├── PROJECT.md          # Project identity, goals, context
├── REQUIREMENTS.md     # Numbered requirements
├── ROADMAP.md          # Milestones and phases
├── STATE.md            # Current project state (auto-maintained)
├── config.json         # GSD configuration
├── CLAUDE.md           # Claude-specific context (auto-discovered)
├── phases/
│   └── {NN}-{slug}/
│       ├── {phase}-CONTEXT.md       # From /gsd-discuss-phase
│       ├── {phase}-RESEARCH.md      # From /gsd-plan-phase
│       ├── {phase}-{N}-PLAN.md      # Execution plans
│       ├── {phase}-{N}-SUMMARY.md   # Post-execution summaries
│       ├── {phase}-VERIFICATION.md  # Verification results
│       └── {phase}-UAT.md           # UAT results
├── intel/              # Codebase intelligence (from /gsd-map-codebase)
├── graphs/             # Knowledge graph (from /gsd-graphify)
├── spikes/             # Feasibility experiments
├── sketches/           # UI mockups
├── learnings/          # Extracted patterns
├── seeds/              # Forward-looking ideas
├── todos/              # Captured tasks
└── reports/            # Milestone summaries, session reports
```

---

## Architecture

```
get-shit-done/bin/lib/    # Core Node.js library (CommonJS .cjs, no external deps)
get-shit-done/workflows/  # Workflow definition files (.md)
agents/                   # Agent definition files (.md)
commands/gsd/             # Slash command definitions (.md)
.claude-plugin/           # Claude Code plugin configuration
tests/                    # Test files (.test.cjs, node:test + node:assert)
```

**Coding standards (for contributing):**
- CommonJS only — `require()`, never `import`
- No external dependencies in core — Node.js built-ins only
- Test framework: `node:test` and `node:assert` ONLY
- File extensions: `.cjs` for all test and lib files
- Security: use `execFileSync` (array args) not `execSync` (string interpolation)

---

## Configuration Reference (key settings)

| Key | Description |
|-----|-------------|
| `workflow.research` | Enable/disable research step |
| `workflow.plan_check` | Enable/disable plan checker |
| `workflow.verifier` | Enable/disable verification |
| `workflow.tdd_mode` | Require failing test before fix |
| `workflow.mvp_mode` | MVP vertical-slice planning mode |
| `workflow.cross_ai_execution` | Delegate execution to external AI CLI |
| `workflow.cross_ai_command` | External AI CLI command |
| `workflow.subagent_timeout` | Timeout for subagent execution |
| `workflow.auto_prune_state` | Auto-prune stale state |
| `workflow.plan_bounce` | External plan bounce validation |
| `git.base_branch` | Base branch for PRs |
| `git.phase_branch_template` | Branch naming template |
| `graphify.enabled` | Enable knowledge graph |
| `graphify.auto_update` | Auto-rebuild graph after HEAD-advancing ops |
| `audit.enabled` | Enable GSD_AUDIT trace log |
| `response_language` | Language for GSD responses |
| `context_window` | Context window size hint |
| `intel.enabled` | Enable queryable codebase intel |

Config location: `.planning/config.json` (per-project) or `~/.gsd/defaults.json` (global defaults)

---

## Package Legitimacy Gate (v1.42.1)

When the researcher recommends external packages, `slopcheck install <pkg> --json` is run on each one:

| Verdict | Action |
|---------|--------|
| `[SLOP]` | Package removed from RESEARCH.md entirely; never reaches planner |
| `[SUS]` | Package flagged; planner inserts `checkpoint:human-verify` before install task |
| `[OK]` | Package approved; no checkpoint added |
| `[ASSUMED]` | Package from WebSearch; treated as `[SUS]`, gets human checkpoint |

Executor will NOT auto-install a similarly-named alternative if an install fails — always confirm first.

---

## MVP Mode

Phase-level planning mode framing work as vertical slices (UI → API → DB) of one user-visible capability instead of horizontal layers.

Resolved via: `--mvp` CLI flag → `**Mode:** mvp` in ROADMAP.md → `workflow.mvp_mode` config → false

**Phase 1 on new MVP project** → Walking Skeleton: the thinnest end-to-end stack proving every layer works together. Emitted as `SKELETON.md`.

**Story format:** `As a [role], I want to [capability], so that [outcome].`

**SPIDR Splitting** (when story too large): Spike · Paths · Interfaces · Data · Rules

---

## Context Engineering Concepts

| Term | Meaning |
|------|---------|
| Context rot | Quality degradation as AI fills its context window |
| Subagent | Fresh-context executor; starts with clean 200k-token context |
| Walking skeleton | Phase 1 deliverable proving the full stack works end-to-end |
| Vertical slice | Single-feature task from open-to-close, end-to-end |
| STATE.md | Source of truth for project state across sessions |
| Workstream | Isolated parallel work area with its own `.planning/` state |

---

## Checkpoint Heartbeats

Background `execute-phase` runs emit `[checkpoint]` markers at every wave and plan boundary to prevent API SSE stream idle timeouts:

```
[checkpoint] phase {N} wave {W}/{M} starting, {count} plan(s), {P}/{Q} plans done
[checkpoint] phase {N} wave {W}/{M} plan {plan_id} starting ({P}/{Q} plans done)
[checkpoint] phase {N} wave {W}/{M} plan {plan_id} complete ({P}/{Q} plans done)
[checkpoint] phase {N} wave {W}/{M} complete, {P}/{Q} plans done ({ok}/{count} ok)
```

---

## State CLI Tools

```bash
node gsd-tools.cjs state validate              # Detect drift between STATE.md and filesystem
node gsd-tools.cjs state sync                  # Reconstruct STATE.md from disk
node gsd-tools.cjs state sync --verify         # Dry-run: show changes without writing
node gsd-tools.cjs state planned-phase --phase N --plans N
node gsd-tools.cjs graphify build|query|status|diff|snapshot
node gsd-tools.cjs update-context --json       # Resolve installed version + scope
node gsd-tools.cjs migrate-config              # Explicit on-disk config migration
```

---

## Community

| Resource | Link |
|----------|------|
| GitHub | https://github.com/open-gsd/gsd-core |
| Discord | https://discord.gg/mYgfVNfA2r |
| npm | https://www.npmjs.com/package/@opengsd/gsd-core |
| Docs | https://github.com/open-gsd/gsd-core/blob/next/docs/README.md |

---

## Quick-Start Cheatsheet

```bash
# Install
npx @opengsd/gsd-core@latest

# New project
/gsd-new-project

# The loop (repeat per phase)
/gsd-discuss-phase N     # optional — clarify unknowns
/gsd-plan-phase N        # research + plan
/gsd-execute-phase N     # build
/gsd-verify-work N       # UAT
/gsd-ship N              # PR

# Navigation
/gsd-progress            # where am I?
/gsd-progress --next     # auto-advance
/gsd-resume-work         # new session

# Quality
/gsd-code-review N --fix
/gsd-debug "description"

# Milestone
/gsd-complete-milestone
/gsd-new-milestone "v2.0"
```
