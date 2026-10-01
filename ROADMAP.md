# DevShell workspace roadmap

Updated: 2026-10-01

## Direction

Evolve the existing project -> terminal -> task/service launcher into a multi-project developer workspace. Keep VS Code as the full editor; DevShell coordinates repositories, sessions, services, browser pages, workflows, and generated artifacts.

The target layout is Projects | Workspace | Contextual Inspector, with a compact status bar for services, Git, environment, ports, and resource usage. Prefer categorized actions and a command palette over an ever-growing list of quick-action pills.

## Existing baseline

- JSON desktop profiles with UI switching and machine-specific folders/environments.
- Multi-repository projects and repository cards with branch, changes, upstream counts, and environment checks.
- Managed Build/Run jobs with live output, persistent logs, Stop, and owned process trees.
- Protected Clone/Fetch/Pull and an Update All queue, using fast-forward pulls without automatic resets or commits.
- Jupyter service startup, status, logs, and authenticated browser opening.
- Embedded browser tabs with independent navigation, per-profile restoration, and token-free saved URLs.
- Math3D Build + Run + Open, HTTP/worker readiness checks, startup timeout, and occupied-port protection.

Implementation does not imply runtime verification. Browser/workflow changes still need a focused manual check before being called complete.

## Delivery groups

### Group 1: Repositories as first-class objects

Status: in progress. Begin with a read-only repository detail/action slice.

- [ ] Show latest commit hash, subject, author, and timestamp.
- [ ] Show fetch/push remotes and linked worktrees, including detached/locked/prunable state.
- [ ] Add Diff and History actions with captured output, cancellation, and no external Git diff helpers.
- [ ] Add Open GitHub using the embedded browser.
- [ ] Add a compact repository strip for the selected project above its workspace.
- [ ] Add repository selection for multi-repository projects, including Jupyter workspaces with an actual Git root.
- [ ] Add explicit Commit/Push flows with selected/staged files, commit-message entry, destination preview, and confirmation.
- [ ] Validate clean/dirty, unborn/detached, missing-root, multiple-remote, Unicode-path, and worktree cases.

Acceptance: repository state and read-only inspection are available without leaving DevShell; write actions are deliberate, scoped, and never silently stash, reset, force-push, or commit unrelated files. Partial metadata failures must not disable existing Build/Run actions.

### Group 2: Browser and mixed workspace tabs

Status: browser-tab foundation implemented; mixed center workspace pending.

- [x] Separate browser pages with New/Close tab and navigation controls.
- [x] Restore browser tabs and visibility per profile without persisting URL authentication tokens.
- [x] Open ready local applications from repository launch actions.
- [ ] Unify center tab types: Terminal, Browser, Jupyter, Diff, Markdown, Files, and Logs.
- [ ] Add Copy URL, DevTools, project URL shortcuts, and device-size presets.
- [ ] Let service records advertise Open actions once healthy.
- [ ] Validate restoration, profile isolation, hide/show, popup links, failed navigation, and local services that are not running.

Acceptance: GitHub, Jupyter, local apps, reports, and documentation coexist in the workspace rather than replacing one page or requiring external windows.

### Group 3: Generalized Tasks and Services

Status: planned; build on managed jobs and the Jupyter controller.

- [ ] Separate finite Tasks from long-running Services and sequencing Workflows.
- [ ] Give services explicit commands, cwd, environment, readiness checks, and URLs.
- [ ] Expose Running/Stopped/Failed, PID, ports, uptime, CPU/RAM, Open, Logs, Restart, and Stop.
- [ ] Define ownership, restart/reuse, app-close behavior, and occupied-port rules before adding adapters.
- [ ] Adapt Jupyter, Vite, APIs, and workers to the same lifecycle model.

Acceptance: each managed service has a clear owner and observable lifecycle; unrelated processes are never killed or reused merely because their port matches.

### Group 4: Declarative project manifests

Status: planned.

- [ ] Define a versioned `devshell.project.json` schema for repositories, terminals, tasks, services, URLs, health checks, artifacts, and workflows.
- [ ] Keep shared project definitions separate from machine/profile path and environment overrides.
- [ ] Validate schemas and references with actionable errors; document migration from current profile JSON.
- [ ] Import a project from a folder or repository without hard-coded Math3D/Jupyter/Theory behavior.

Acceptance: a project can describe its own setup and useful actions, while profiles only supply host-specific overrides. Imported commands remain visible and require a deliberate action to execute.

### Group 5: Contextual Inspector and status bar

Status: planned.

- [ ] Follow the selected terminal, repository, browser page, service, task, or artifact.
- [ ] Show relevant cwd/process/environment, Git actions, URL/service/port, notebook/kernel, or command/result details.
- [ ] Add a compact status bar for running services, Git state, environment summary, ports, and resource usage.
- [ ] Replace dense QUICK pills with a categorized command palette: Start, Open, Build, Test, Validate, Tools.
- [ ] Keep only 4-6 pinned/frequently used actions visible by default.

Acceptance: the right panel explains the selected object rather than accumulating every project's controls.

### Group 6: Workflows, history, and run results

Status: planned.

- [ ] Define sequences such as Install -> Validate -> Test -> Start, with explicit failure gating and cancellation.
- [ ] Retain task timestamps, duration, exit code, result summaries, and a bounded log history.
- [ ] Open results in workspace Logs/Markdown tabs and link produced artifacts.
- [ ] Support rerunning failed steps without duplicating already-running services.

Acceptance: users can see what ran, why it failed, and what to run next without reconstructing a terminal transcript.

### Group 7: Named sessions, Files/Artifacts, and broader health

Status: planned; incremental support work for the other groups.

- [ ] Named terminal sessions with cwd, shell, environment, startup command, rename, pin, duplicate, restart, splits, and New terminal here.
- [ ] Restore session definitions safely; never replay arbitrary startup commands silently.
- [ ] Show recent/project files and generated PDFs, screenshots, reports, benchmark JSON, installers, and build outputs.
- [ ] Provide Open, Reveal, Copy path, and Open in VS Code without implementing a full IDE.
- [ ] Expand health checks to Node/npm/pnpm, Python/venv, Git, Docker, .NET, Java, GPU/CUDA, environment variables, ports, and dependencies.
- [ ] Summarize healthy environments compactly and expand failures only when actionable.

Acceptance: common workspace operations stay discoverable and portable without making the interface dense or host-specific.

## Delivery rules

- Keep current profile/task behavior compatible while introducing new capabilities.
- Ship small end-to-end slices; update this roadmap as implementation and verification progress.
- Persist profile-scoped workspace state separately from shared project configuration.
- Keep web content separate from the native launcher bridge and host objects.
- Redact credentials and tokens from displayed/saved URLs and remote metadata.
- Keep Git reads local unless a user explicitly requests a remote operation; label ahead/behind counts as last-fetched data.
- Run builds/tests/manual checks only when requested; report unverified changes clearly.
- Do not automatically install packages, mutate Git state, or terminate unrelated services.

## Immediate next slice

Start Group 1 with last-commit/remotes/worktrees metadata and Diff/History/Open GitHub actions on existing repository cards. Use existing managed job logs for read-only inspection until Group 2 provides center Diff/Logs tabs. Keep Commit/Push and the compact selected-project strip as subsequent slices, not hidden side effects of this one.
