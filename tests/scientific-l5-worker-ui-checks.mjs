// Opt-in desktop acceptance: fresh lower qualifications and fixed L5 worker cases.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')

async function newRun(previous, recipe) {
  const deadline = Date.now() + 360_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      if (!existsSync(join(folder, 'results.json'))) continue
      try {
        const result = JSON.parse(readFileSync(join(folder, 'results.json'), 'utf8'))
        if (result.recipeId !== recipe) continue
        const qualification = existsSync(join(folder, 'qualifications.json'))
          ? JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8')) : null
        return { folder, result, qualification }
      } catch { /* Wait for saved evidence. */ }
    }
    await delay(1000)
  }
  throw new Error(`${recipe} did not finish before timeout`)
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9239')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  const detail = main.getByRole('region', { name: /runtime details/ })
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  const history = main.getByRole('region', { name: 'Scientific run history' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  for (const [name, id, capability, output] of [
    ['CGAL', 'cgal-win-conda', 'mesh.validate', 'l5-positive.obj'],
    ['VTK', 'vtk-win-conda', 'mesh.read', 'l5-positive.vtp']
  ]) {
    await main.locator('.scientific-runtime-item').filter({ hasText: name }).first().click()
    await nav.getByRole('button', { name: 'Commands' }).click()
    let l5Run
    for (const [button, recipe, level] of [
      ['Probe in runtime-lab', 'lab.probe', 'L3'],
      ['Compile & link', 'compile-link', 'L4'],
      ['Run L5 worker check', 'l5.worker', 'L5'],
      ['Run L6 reproduction check', 'l6.reproduce', 'L6']
    ]) {
      const previous = new Set(readdirSync(runs))
      await detail.getByRole('button', { name: button, exact: true }).click()
      const { folder, result, qualification } = await newRun(previous, recipe)
      assert.equal(result.runtimeId, id)
      assert.equal(result.state, 'succeeded', result.diagnostics?.map(item => item.message).join('; '))
      assert.ok(qualification?.records.some(item => item.level === level), `${id} needs ${level}`)
      if (recipe === 'l5.worker') {
        l5Run = result
        const record = qualification.records.find(item => item.level === 'L5' && item.capabilityId === capability)
        assert.ok(record)
        assert.equal(record.lowerQualification.records.length, 5)
        assert.equal(result.l5Evidence.positive.state, 'succeeded')
        assert.equal(result.l5Evidence.rejection.state, 'failed')
        assert.equal(result.l5Evidence.rejection.outputAbsent, true)
        assert.equal(result.l5Evidence.positive.artifactPath, `positive/${output}`)
        assert.ok(result.artifacts.some(item => item.path === `positive/${output}`
          && item.sha256 === result.l5Evidence.positive.artifactSha256))
        assert.ok(existsSync(join(folder, 'positive', output)))
        await nav.getByRole('button', { name: 'History' }).click()
        await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
        const summary = history.locator('section[aria-label="Current qualification summary"]')
        const row = summary.locator('tr').filter({ hasText: capability })
        await row.waitFor()
        assert.match(await row.innerText(), /L5|L6/)
        await history.locator(`tr[data-run-id="${result.runId}"]`).getByRole('button', { name: 'Result' }).click()
        const view = history.locator('section[aria-label="Qualification records"]')
        await view.getByText(capability).waitFor()
        assert.match(await view.innerText(), /current/)
        await nav.getByRole('button', { name: 'Commands' }).click()
      }
      if (recipe === 'l6.reproduce') {
        assert.ok(l5Run)
        const comparison = result.l6Evidence
        assert.equal(comparison.verdict, 'matched')
        assert.equal(comparison.baseline.runId, l5Run.runId)
        assert.equal(comparison.baseline.artifactSha256, comparison.positive.artifactSha256)
        assert.equal(comparison.baseline.artifactSha256, l5Run.l5Evidence.positive.artifactSha256)
        assert.equal(comparison.rejection.state, 'failed')
        assert.equal(comparison.rejection.outputAbsent, true)
        assert.equal(comparison.roundTrip.points, 4)
        assert.equal(comparison.roundTrip.triangles, 4)
        assert.equal(comparison.roundTrip.boundaryEdges, 0)
        assert.equal(comparison.roundTrip.nonManifoldEdges, 0)
        assert.equal(comparison.roundTrip.closed, true)
        assert.deepEqual(comparison.roundTrip.bounds, [-1, 1, -1, 1, -1, 1])
        assert.ok(result.artifacts.some(item => item.path === 'reload/results.json'
          && item.sha256 === comparison.roundTripResultSha256))
        assert.ok(qualification.records.some(item => item.level === 'L6' && item.capabilityId === capability))
        await nav.getByRole('button', { name: 'History' }).click()
        await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
        const row = history.locator('section[aria-label="Current qualification summary"] tr').filter({ hasText: capability })
        await row.waitFor()
        assert.match(await row.innerText(), /L6/)
        await row.getByRole('button', { name: result.runId.slice(0, 12) }).click()
        const view = history.locator('section[aria-label="L6 reproduction evidence"]')
        await view.getByText('L6 artifact reproduction: matched').waitFor()
        assert.match(await view.innerText(), new RegExp(l5Run.runId.slice(0, 12)))
        await view.getByRole('button', { name: l5Run.runId.slice(0, 12) }).click()
        await history.locator('.scientific-history-result').getByText(l5Run.runId, { exact: true }).waitFor()
        const l5Row = history.locator('section[aria-label="Qualification records"] tr').filter({ hasText: capability }).filter({ hasText: 'L5' })
        assert.match(await l5Row.innerText(), /current/)
        await nav.getByRole('button', { name: 'Commands' }).click()
      }
      console.log(`${id} ${recipe}: ${result.runId} / ${level}`)
    }
    if (id === 'vtk-win-conda') {
      const previous = new Set(readdirSync(runs))
      await detail.getByRole('button', { name: 'Run L7 MATH3D handoff' }).click()
      const { result, qualification } = await newRun(previous, 'l7.math3d-import')
      assert.equal(result.runtimeId, id)
      assert.equal(result.state, 'succeeded', result.diagnostics?.map(item => item.message).join('; '))
      assert.ok(qualification?.records.some(item => item.level === 'L7' && item.capabilityId === 'mesh.interop.math3d'))
      assert.equal(result.l7Evidence.consumer.consumer, 'MATH3D desktop loadSurfaceMeshFromFile')
      assert.equal(result.l7Evidence.consumer.points, 4)
      assert.equal(result.l7Evidence.consumer.triangles, 4)
      assert.equal(result.l7Evidence.consumer.closed, true)
      assert.ok(result.artifacts.some(item => item.path === 'handoff/vtk-math3d.obj'
        && item.sha256 === result.l7Evidence.objSha256))
      await nav.getByRole('button', { name: 'History' }).click()
      await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
      const row = history.locator('section[aria-label="Current qualification summary"] tr').filter({ hasText: 'mesh.interop.math3d' })
      await row.waitFor()
      assert.match(await row.innerText(), /L7/)
      await row.getByRole('button', { name: result.runId.slice(0, 12) }).click()
      await history.locator('section[aria-label="L7 MATH3D handoff evidence"]')
        .getByText('L7 VTK → MATH3D importer').waitFor()
      console.log(`${id} l7.math3d-import: ${result.runId} / L7`)
    }
    if (id === 'cgal-win-conda') {
      const previous = new Set(readdirSync(runs))
      await detail.getByRole('button', { name: 'Run L7 CGAL → VTK → MATH3D' }).click()
      const { result, qualification } = await newRun(previous, 'l7.cgal-vtk-math3d')
      assert.equal(result.state, 'succeeded', result.diagnostics?.map(item => item.message).join('; '))
      assert.ok(qualification?.records.some(item => item.level === 'L7' && item.capabilityId === 'mesh.interop.vtk-math3d'))
      const evidence = result.l7InteropEvidence
      assert.equal(evidence.sourceReload.signedVolume, evidence.vtkConsumer.signedVolume)
      assert.equal(evidence.sourceReload.signedVolume, evidence.math3dConsumer.signedVolume)
      assert.equal(evidence.sourceReload.surfaceArea, evidence.vtkConsumer.surfaceArea)
      assert.equal(evidence.sourceReload.surfaceArea, evidence.math3dConsumer.surfaceArea)
      assert.equal(evidence.rejection.state, 'rejected')
      assert.match(evidence.rejection.reason, /invalid face indices/)
      assert.equal(evidence.consumerContractSha256, qualification.records.find(item => item.level === 'L7').consumerContractSha256)
      await nav.getByRole('button', { name: 'History' }).click()
      await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
      const row = history.locator('section[aria-label="Current qualification summary"] tr').filter({ hasText: 'mesh.interop.vtk-math3d' })
      await row.waitFor()
      assert.match(await row.innerText(), /L7/)
      await row.getByRole('button', { name: result.runId.slice(0, 12) }).click()
      await history.locator('section[aria-label="L7 CGAL interoperability evidence"]')
        .getByText('L7 CGAL → VTK → MATH3D').waitFor()
      await nav.getByRole('button', { name: 'Commands' }).click()
      console.log(`${id} l7.cgal-vtk-math3d: ${result.runId} / L7`)
      const beforeL8 = new Set(readdirSync(runs))
      await detail.getByRole('button', { name: 'Run L8 resilience' }).click()
      const { result: l8, qualification: l8Qualification } = await newRun(beforeL8, 'l8.resilience')
      assert.equal(l8.state, 'succeeded', l8.diagnostics?.map(item => item.message).join('; '))
      assert.ok(l8Qualification?.records.some(item => item.level === 'L8' && item.capabilityId === 'mesh.interop.vtk-math3d'))
      assert.equal(l8.l8Evidence.observations.repeats.length, 3)
      assert.equal(new Set(l8.l8Evidence.observations.repeats.map(item => item.resultSha256)).size, 1)
      assert.equal(l8.l8Evidence.observations.cancellation.state, 'cancelled')
      assert.equal(l8.l8Evidence.observations.timeout.state, 'timed-out')
      assert.equal(l8.l8Evidence.observations.memory.state, 'limited')
      await nav.getByRole('button', { name: 'History' }).click()
      await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
      const l8Row = history.locator('section[aria-label="Current qualification summary"] tr').filter({ hasText: 'mesh.interop.vtk-math3d' })
      await l8Row.waitFor()
      assert.match(await l8Row.innerText(), /L8/)
      await l8Row.getByRole('button', { name: l8.runId.slice(0, 12) }).click()
      await history.locator('section[aria-label="L8 resilience evidence"]')
        .getByText('L8 repeat and limits').waitFor()
      await nav.getByRole('button', { name: 'Commands' }).click()
      console.log(`${id} l8.resilience: ${l8.runId} / L8`)
      const beforeL9 = new Set(readdirSync(runs))
      await detail.getByRole('button', { name: 'Run L9 MATH3D product check' }).click()
      const { result: l9, qualification: l9Qualification } = await newRun(beforeL9, 'l9.math3d-product')
      assert.equal(l9.state, 'succeeded', l9.diagnostics?.map(item => item.message).join('; '))
      assert.ok(l9Qualification?.records.some(item => item.level === 'L9' && item.capabilityId === 'mesh.interop.vtk-math3d'))
      assert.equal(l9.l9Evidence.sourceL8RunId, l8.runId)
      assert.equal(l9.l9Evidence.regression.regression, 'passed')
      assert.equal(l9.l9Evidence.regression.viewerState, 'mounted')
      assert.ok(l9.l9Evidence.regression.blueMeshPixels > 1000)
      assert.equal(l9.l9Evidence.regression.points, 4)
      assert.equal(l9.l9Evidence.regression.triangles, 4)
      for (const path of ['positive/l5-positive.obj', 'handoff/handoff.json', 'product/mesh-document.json',
        'product/mesh-resource.bin', 'product/viewer.png', 'product/regression.json'])
        assert.ok(l9.artifacts.some(item => item.path === path), `L9 needs ${path}`)
      await nav.getByRole('button', { name: 'History' }).click()
      await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
      const l9Row = history.locator('section[aria-label="Current qualification summary"] tr').filter({ hasText: 'mesh.interop.vtk-math3d' })
      await l9Row.waitFor()
      assert.match(await l9Row.innerText(), /L9/)
      await l9Row.getByRole('button', { name: l9.runId.slice(0, 12) }).click()
      await history.locator('section[aria-label="L9 MATH3D product evidence"]')
        .getByText('L9 MATH3D Mesh document and viewer').waitFor()
      await nav.getByRole('button', { name: 'Commands' }).click()
      console.log(`${id} l9.math3d-product: ${l9.runId} / L9`)
    }
  }
  await main.locator('.scientific-runtime-item').filter({ hasText: 'Gmsh' }).first().click()
  assert.equal(await detail.getByRole('button', { name: 'Run L5 worker check' }).count(), 0)
  assert.equal(await detail.getByRole('button', { name: 'Run L6 reproduction check' }).count(), 0)
  assert.equal(await detail.getByRole('button', { name: 'Run L7 MATH3D handoff' }).count(), 0)
  assert.equal(await detail.getByRole('button', { name: 'Run L7 CGAL → VTK → MATH3D' }).count(), 0)
  assert.equal(await detail.getByRole('button', { name: 'Run L8 resilience' }).count(), 0)
  assert.equal(await detail.getByRole('button', { name: 'Run L9 MATH3D product check' }).count(), 0)
  await nav.getByRole('button', { name: 'History' }).click()
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  await history.locator('section[aria-label="Current qualification summary"]')
    .getByText('No current qualifications for this provider.').waitFor()
  console.log('PASS: CGAL L9 product gate, VTK L7 handoff, Gmsh unqualified')
} finally {
  await browser.close()
}
