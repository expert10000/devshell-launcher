import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fixtures, referenceMesh, transform } from '../tools/math3d-boolean-fixtures.mjs';
import { meshStats, numericComparison } from '../tools/math3d-mesh-comparison.mjs';

const cube = { vertices: [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],
  faces: [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]] };
const expected = {
  overlapping: [[12,32,1], [4,16,1], [4,16,1]],
  touching: [[16,40,1], [0,0,0], [8,24,1]],
  disjoint: [[16,48,2], [0,0,0], [8,24,1]],
  contained: [[8,24,1], [1,6,1], [7,30,2]],
};
for (const relation of Object.keys(expected)) test(`${relation} analytic boundaries have expected volume, area, and shells`, () => {
  fixtures.filter(item => item.relation === relation).forEach((fixture, index) => {
    const stats = meshStats(referenceMesh(cube, fixture));
    const [volume, area, shells] = expected[relation][index];
    assert.ok(Math.abs(stats.volume - volume) < 1e-10);
    assert.equal(stats.area, area);
    assert.equal(stats.components, shells);
    assert.equal(stats.euler, shells * 2);
    assert.equal(stats.closed, shells > 0);
    if (!shells) assert.equal(stats.bounds, null);
  });
});
test('geometry comparisons reject a shifted result even if topology matches', () => {
  const wrong = transform(cube, 1, 0.1);
  const comparison = numericComparison(cube, wrong, meshStats(cube), meshStats(wrong));
  assert.ok(comparison.metrics.boundsDelta > comparison.tolerances.bounds);
  assert.ok(comparison.metrics.sampledSurfaceDeviation > comparison.tolerances.sampledSurface);
});
test('empty intersections compare finitely and reject nonempty output', () => {
  const empty = { vertices: [], faces: [] };
  const stats = meshStats(empty);
  const same = numericComparison(empty, empty, stats, stats);
  assert.ok(Object.values(same.metrics).every(value => value === 0));
  const wrong = numericComparison(empty, cube, stats, meshStats(cube));
  assert.ok(wrong.metrics.volumeDelta > wrong.tolerances.volume);
  assert.ok(wrong.metrics.sampledSurfaceDeviation > wrong.tolerances.sampledSurface);
});
test('cavity orientation changes enclosed volume, not surface area', () => {
  const fixture = fixtures.find(item => item.relation === 'contained' && item.operation === 2);
  const cavity = referenceMesh(cube, fixture);
  const wrong = { ...cavity, faces: cavity.faces.map((face, i) => i < 12 ? face : [...face].reverse()) };
  const comparison = numericComparison(cavity, wrong, meshStats(cavity), meshStats(wrong));
  assert.equal(comparison.metrics.areaDelta, 0);
  assert.ok(comparison.metrics.volumeDelta > comparison.tolerances.volume);
});
