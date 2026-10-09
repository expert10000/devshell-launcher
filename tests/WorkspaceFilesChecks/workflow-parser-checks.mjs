import assert from 'node:assert/strict'
import { parseBuildDiagnostics } from '../../DevShell/ui/dev-ui-react/src/diagnosticParser.ts'
import { singleWorkspacePane, splitWorkspacePane, resolveWorkspaceSplit, chooseWorkspacePane, resizeWorkspacePanes } from '../../DevShell/ui/dev-ui-react/src/workspaceSplit.ts'
import { restoreWorkspaceDescriptors } from '../../DevShell/ui/dev-ui-react/src/passiveWorkspaceLayout.ts'
import { compareTextLines } from '../../DevShell/ui/dev-ui-react/src/artifactComparisonState.ts'
let checks = 0; const pass = name => { checks++; console.log('PASS: ' + name) }
const diagnostics = parseBuildDiagnostics('C:\\repo\\source.cs(12,4): error CS1002: Expected ;\nsrc/app.ts:8:2 - warning TS1: fixture\nerror[E1]: Rust fixture\n --> src/main.rs:7:9\nFile "py/main.py", line 6, in run\n  explode()\nmain.tex:14: Undefined command\nmain.cpp:11:3: error: missing value')
assert.equal(diagnostics.items[0].line, 12); assert.equal(diagnostics.items[0].column, 4); pass('.NET diagnostic file/line/column')
assert.equal(diagnostics.items[1].severity, 'warning'); assert.equal(diagnostics.items[1].column, 2); pass('TypeScript warning locations')
assert.equal(diagnostics.items[2].file, 'src/main.rs'); assert.equal(diagnostics.items[2].column, 9); assert.equal(diagnostics.items[2].message, 'Rust fixture'); pass('Rust arrow location preserves column and message')
assert.equal(diagnostics.items[3].line, 6); assert.match(diagnostics.items[3].message, /explode/); pass('Python traceback source location')
assert.equal(diagnostics.items[4].file, 'main.tex'); assert.equal(diagnostics.items[5].column, 3); pass('TeX and C++ diagnostics')
assert.equal(parseBuildDiagnostics('12:42:30\nhttp://localhost:1234\nPORT:4000:ready').items.length, 0); pass('Ports, timestamps, and URLs are not file diagnostics')
assert.equal(parseBuildDiagnostics('a.cs(3): error E: same\na.cs(3): error E: same').items.length, 1); pass('Duplicate diagnostics removed')
const capped = parseBuildDiagnostics(Array.from({ length: 110 }, (_, i) => `a.cs(${i + 1}): error E: fixture`).join('\n')); assert.equal(capped.items.length, 100); assert.ok(capped.truncated); pass('Diagnostic scan bounded')
const single = singleWorkspacePane('p', 'a'); const split = splitWorkspacePane(single, 'right', ['a', 'b'], 'a'); assert.equal(split.secondaryId, 'b'); pass('Split chooses a distinct secondary tab')
assert.equal(resolveWorkspaceSplit(split, 'p', ['a', 'b'], 'b').focused, 'secondary'); pass('Tab selection focuses the correct pane')
assert.equal(resolveWorkspaceSplit(split, 'other', ['a', 'b'], 'a').direction, null); pass('Profile switching resets session split')
assert.equal(resolveWorkspaceSplit(split, 'p', ['a'], 'a').direction, null); pass('Closing a split tab safely collapses')
assert.equal(chooseWorkspacePane(split, 'primary', 'b').secondaryId, 'a'); pass('Choosing the other view swaps slots without duplicates')
assert.equal(resizeWorkspacePanes(split, 95).ratio, 80); pass('Divider ratio is clamped')
const inputs = [{ kind: 'files', projectId: 'p', repositoryId: 'r', filePath: '', activationId: 'must-not-replay', revealPath: 'secret.cs', sourceLine: 7 }, { kind: 'logs', projectId: 'p', repositoryId: 'r' }]
const restored = restoreWorkspaceDescriptors([], inputs, 'secondary'); assert.equal(restored.error, ''); assert.ok(restored.tabs.every(tab => tab.restored && !tab.activationId && !tab.revealPath && !tab.sourceLine)); pass('Fresh layout descriptors are passive and strip replay intents')
const existing = { id: 'kept', kind: 'files', projectId: 'p', repositoryId: 'r', filePath: 'current', activationId: 'old' }; const reused = restoreWorkspaceDescriptors([existing], inputs); assert.equal(reused.tabs[0].id, 'kept'); assert.equal(reused.tabs[0].filePath, 'current'); assert.equal(existing.activationId, 'old'); pass('Existing previews are reused without mutating their descriptors')
assert.ok(restoreWorkspaceDescriptors([], [inputs[0], inputs[0]]).error); assert.ok(restoreWorkspaceDescriptors([], [{ ...inputs[0], filePath: '../outside' }, inputs[1]]).error); pass('Invalid and duplicate layout views rejected')
const difference = compareTextLines('one\r\ntwo', 'one\nchanged'); assert.equal(difference.changed, 1); assert.equal(difference.rows[0].line, 2); pass('Report comparison normalizes line endings')
assert.equal(compareTextLines('same', 'same').changed, 0); pass('Identical reports have no differences')
const bounded = compareTextLines(Array(5100).fill('a').join('\n'), Array(5100).fill('b').join('\n')); assert.equal(bounded.rows.length, 100); assert.ok(bounded.truncated); pass('Report difference display bounded')
console.log(`${checks} workflow parser checks passed`)
