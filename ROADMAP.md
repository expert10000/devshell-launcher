# DevShell workspace roadmap

Updated: 2026-10-28

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

Status: implemented, with focused backend and Playwright checks passed. Remaining write-action and edge-case verification is listed below; Group 1 is not yet fully signed off.

- [x] Show latest commit hash, subject, author, and timestamp.
- [x] Show fetch/push remotes and linked worktrees, including detached/locked/prunable state.
- [x] Add Diff and History actions with captured output, cancellation, and no external Git diff helpers.
- [x] Add Open GitHub using the embedded browser.
- [x] Add a compact repository strip for the selected project above its workspace.
- [x] Add repository selection for multi-repository projects, including Jupyter workspaces with an actual Git root.
- [x] Surface missing declared project/repository tools before Clone, with explicit managed WinGet install actions; Clone creates missing parent folders and preserves occupied non-Git destinations.
- [x] Add explicit Commit/Push flows with selected/staged files, commit-message entry, destination preview, and confirmation.
- [x] Add a Changes panel with separate working/staged file lists, per-file previews, and Stage selected / Unstage selected.
- [x] Keep partial staging visible on both sides; preserve working edits when unstaging; never stage everything or discard edits automatically.
- [ ] Validate clean/dirty, unborn/detached, missing-root, multiple-remote, Unicode-path, and worktree cases.
- [ ] Verify actual Commit/Push execution and push-confirmation cancellation against disposable local repositories, including stale-preview rejection.
- [ ] Verify launcher exit/restart after native Git confirmation dialogs are dismissed.

Acceptance: repository state and read-only inspection are available without leaving DevShell; write actions are deliberate, scoped, and never silently stash, reset, force-push, or commit unrelated files. Partial metadata failures must not disable existing Build/Run actions.

Delivered and checked on 2026-10-01:

- Git dashboard checks passed: clean/no-upstream state, rename and Unicode paths, diverged counts, detached HEAD, invalid roots, and missing tools.
- Managed job checks passed: successful Build/Run sequencing, failed-build gating, captured logs, duplicate prevention, Stop, and owned child-process lifecycle.
- New `tests/RepositoryChangesChecks` passed: selective staging, preservation of edits on unstage, unborn HEAD, partial staging, Unicode, renames, deletions, stale-index rejection, literal pathspecs, path-escape rejection, binary previews, and active-operation blocking.
- Playwright checks against the actual launcher and a disposable repository passed: working/staged diffs, selected staging into the real index, partial staging on both sides, unstaging without losing edits, and untracked text previews.
- Playwright also checked the narrow Changes layout, the five-repository selector, Theory selection, expanded remotes/worktrees, and Jupyter's containing-repository strip.
- Native Commit preview showed only the staged file, disabled submission for an empty message, and was cancelled without creating a commit. This does not verify successful Commit/Push execution.
- Fixed the Changes handler's request-lifetime failure by cloning its JSON payload before asynchronous Git checks; rebuilt and retested the affected UI flow.
- Frontend and launcher builds succeeded. No application tests committed or pushed changes to the user's repositories; write tests used disposable fixtures.
- Theory's configured GitHub URL matches its Git remote. Authenticated GitHub metadata confirmed it is private; the embedded browser requires an interactive sign-in with an account that has access. No URL correction or credential injection was made.

### Group 2: Browser and mixed workspace tabs

Status: Browser and Jupyter now use the existing native browser in center workspace tabs. Logs/Diff and focused PDF/Files acceptance passed; real Math/Theory document cases remain.

- [x] Separate browser pages with New/Close tab and navigation controls.
- [x] Restore browser tabs and visibility per profile without persisting URL authentication tokens.
- [x] Open ready local applications from repository launch actions.
- [x] Add persistent workspace Logs tabs with current-session output, job status, Stop, and Open full log; closing a view does not stop the job.
- [x] Add read-only workspace Diff tabs with file selection, working/staged comparison, Refresh, and opening a preview from Changes.
- [x] Restore validated tab descriptors per profile without saving log/diff contents or replaying jobs, Git writes, or service startup.
- [x] Link browser/Jupyter openings into workspace navigation while keeping the existing native browser pane and authenticated service controller.
- [x] Display Browser/Jupyter pages in the selected center workspace tab, using the existing native browser and Jupyter service controls.
- [x] Add PDF workspace entries with Open/Refresh/Open externally, an explicitly saved Go-to-page target, and native document navigation/zoom/search controls.
- [x] Route Theory's repository/quick-task Open PDF and build-success opening into the native viewer; refresh a visible PDF after a successful managed build.
- [x] Restrict PDF requests to one validated relative PDF within a configured checkout, rejecting path traversal and symlinks/junctions; disable the launcher bridge, permissions, document links, and downloads.
- [x] Preserve only relative PDF paths and explicit page targets in profile tab descriptors; do not replay opening or builds on restoration.
- [x] Add Math Build PDFs using its existing BUILD_ALL.ps1 (volumes, available editions, and QA), plus a bounded build/pdf selector with explicit Open/Refresh list and separate Open in VS Code. Existing Math desktop profiles gain these defaults without rewriting their JSON paths.
- [x] Refresh an already-open PDF collection after a new successful managed build, without replaying a completed job when a tab is restored.
- [x] Add PDF entries to the folder browser, routed into workspace/native viewing without changing terminal cwd. Only configured repository files can be opened; other PDFs remain disabled with an explanatory tooltip.
- [x] Normalize null/absent PDF collection paths to the same frontend identity so reopening a restored selector reuses its tab.
- [x] Add Files and Build PDFs/Open PDF actions directly to the repository strip.
- [x] Add standalone Files & Artifacts workspace tabs with repository switching, folder navigation, filename/artifact filters, bounded read-only text previews, and PDF opening; no terminal session is needed.
- [x] Restore Files folder descriptors without saving previews or search contents. Scoped requests block Git internals, path escapes, and symlink/junction traversal.
- [x] Run WorkspaceFilesChecks, including Logs/Diff descriptor normalization.
- [x] Run focused PDF/Files UI flow checks with a disposable repository, including missing files, collection refresh, page selection, profile isolation, and passive restart restoration.
- Math's user-run build completed on 2026-10-03: 20 PDFs collected under build/pdf, all eight canonical volumes passed document QA, and the managed job exited 0. The stale selector did not automatically refresh; the auto-refresh fix and folder-PDF changes are not yet rebuilt or UI-tested.
- [ ] Build and check Math's PDF collection, empty/missing output, volume selection, build/QA failures, profile restoration, and preservation of its VS Code action. No Math document builds have been run as part of this implementation.
- [ ] Build and check PDF display, large Theory output, native toolbar controls, refreshed output after rebuild, missing/invalid PDFs, explicit page restoration, profile isolation, and external opening. Native scrolling is not tracked in this first version.
- [x] Build and check Logs output/status, Stop and full-log requests, Diff side switching/Refresh, and terminal preservation in the live UI with simulated bridge replies.
- [x] Check Logs/Diff restoration and profile isolation after process restart, passive Browser/Jupyter selection, and failed browser navigation in the live app.
- [x] Check Logs Stop against a real disposable managed job in the live UI.
- [ ] Check authenticated Jupyter reopen after restart.
- [ ] Unify center tab types: Terminal, Browser, Jupyter, Diff, Markdown, Files, and Logs.
- [ ] Add Copy URL, DevTools, project URL shortcuts, and device-size presets.
- [ ] Let service records advertise Open actions once healthy.
- [x] Check center Browser/Jupyter switching, passive restart/profile restoration, failed local navigation, and token-safe saved URLs.
- [ ] Check native hide/show and popup links for center Browser/Jupyter tabs.

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

Delivered 2026-10-27: the inspector now has a profile-wide Services view for configured Jupyter and managed web services, with status, port, Open, Logs, Restart, and Stop. Jupyter logs are bounded and redact authentication tokens. The Tasks view replaces Quick pills with search and collapsible groups, using task-name prefixes when no group is configured. The Windows build and live Playwright checks passed Jupyter lifecycle and task filtering; a separate live Math3D check passed service Start, Open, Logs, Restart, and Stop. The real missing-PowerShell installation check still awaits a clean Windows VM.

Scientific-runtime laboratory: see [SCIENTIFIC_RUNTIMES_ROADMAP.md](SCIENTIFIC_RUNTIMES_ROADMAP.md). Start with the dedicated Scientific Runtimes workspace, then implement validated runtime profiles and explicit environment probes. CGAL and VTK environment definitions must remain separate from proof of installation or capability readiness.

Delivered workspace additions through 2026-10-09:

- [x] Read-only code, static HTML, notebook, image, structured JSON, and CSV/TSV previews.
- [x] Folder history/breadcrumbs, project filename search, artifact overview, recent files, pins, and source/output references.
- [x] Split panes and explicit, profile-scoped named layouts; restoration does not replay commands or reopen documents.
- [x] Clickable bounded compiler diagnostics, including corrected Rust line/column parsing.
- [x] Session-only two-artifact comparison with independent image zoom/pan and bounded line-position report differences.
- [x] Workspace palette (Ctrl+Alt+P) for repository views, file references/search, layouts, and explicitly confirmed managed Build/Run actions.
- Verification: 117 automated backend/parser/viewer checks passed. Frontend and native builds passed; focused live checks covered split sizing, passive named-layout restoration, report/image comparison, and palette confirmation.
- The new comprehensive live workflow harness still needs its guard adjusted: read-only service status polls are not service starts. Do not claim that harness passed.

The older Group 2 acceptance list below remains useful for edge cases; the completed baseline above supersedes its earlier unbuilt status statements.

Verified 2026-10-28: the source frontend and native launcher build. A focused live WebView2 check passed Logs output/status, Stop and full-log requests, tab closing without stopping a job, Diff working/staged switching and Refresh, and terminal preservation. The check simulates bridge replies and performs no Git writes; the separate RepositoryChangesChecks passed against a disposable repository. WorkspaceFilesChecks passed descriptor normalization for Logs/Diff, including rejection of invalid paths and excluding log contents and URL data. A toolbar overlap that blocked closing the last tab was corrected. The combined missing-shell, Jupyter lifecycle, and Logs/Diff UI check passed. Profile restoration/isolation and Browser/Jupyter navigation were checked in the next pass.

Verified 2026-10-28: after a real DevShell process restart, Logs and Diff descriptors restored in the laptop profile with the active Logs tab, no current-session job output, and a passive Diff placeholder. Switching to the portable profile hid those entries; switching back restored them. Selecting saved Jupyter and Browser workspace entries sent no service-start or browser-open request. An invalid browser scheme was rejected, and opening the stopped Math3D URL displayed `ERR_CONNECTION_REFUSED` with `Navigation failed: ConnectionAborted` in the native pane; the workspace remained usable. Reopening a saved browser entry initially lost its repository label; the bridge now carries its repository ID and the frontend preserves existing browser metadata when a URL is reopened. These checks did not exercise a real repository job's Stop button in Logs or an authenticated Jupyter reopen after a restart. The original profile selection and workspace tab descriptors were restored after the check; native browser tabs kept their original IDs and URLs.

Verified 2026-10-28: the isolated Group 2 live harness passed Files preview, refresh, missing-folder recovery, PDF open/refresh, missing-file recovery, collection list refresh to empty and back, explicit page 2, and profile isolation. After a real launcher restart, the PDF and Files descriptors showed passive saved-entry states, the page target remained 2, and Logs had no current-session job. Logs Stop cancelled a real disposable PowerShell build job and left a persistent log. The native PDF viewer loaded both fixture pages at page 2 with page, zoom, and search controls present. External opening, large Theory output, Math's real PDF collection, and authenticated Jupyter reopening remain separate live cases.

Verified 2026-10-28: the existing native browser and authenticated Jupyter service opened in center workspace tabs. Switching Browser, Jupyter, and Logs tabs reused live pages without a new navigation or service action. A real restart restored Browser/Jupyter descriptors passively; switching to the portable profile hid the laptop entries and switching back restored them without replay. The stopped local fixture showed `ERR_CONNECTION_REFUSED` in the native browser and left the workspace usable. Saved workspace and native browser tab JSON omitted a synthetic URL token, query string, and fragment. The test Jupyter service was stopped after the check. Authenticated Jupyter reopening after a restart and the native hide/show button remain separate cases.

Next: complete authenticated Jupyter reopening and the real Math/Theory PDF cases.

- Introduce typed workspace tabs while preserving existing terminal sessions, splits, and profile switching.
- Open job Logs in a persistent workspace tab with live output, exit status, and the existing full-log action.
- Open read-only file Diff tabs with repository, file, and staged/working-side identity; leave staging and commit confirmation in the Changes flow.
- Restore tab descriptors per profile, not captured log/diff contents or authentication tokens. Reopening must not execute Git writes or replay task commands.
- Integrate Browser/Jupyter tab selection with the existing native browser pane in the center workspace while keeping saved descriptors passive.

Before Group 1 sign-off, finish the remaining isolated Commit/Push and multiple-remote/worktree checks above. Do not treat implementation checkmarks as proof that every edge case has been exercised.
