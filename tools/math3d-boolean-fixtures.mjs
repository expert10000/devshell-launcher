const operations = [[1, 'union'], [3, 'intersection'], [2, 'difference']];
export const fixtures = [
  { name: 'Tetrahedron', datasetId: 'math3d/basic/01_tetrahedron.obj', vertices: 4, faces: 4, output: 'math3d-native-self-union.m3dm' },
  { name: 'Cube', datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, output: 'math3d-native-cube-self-union.m3dm' },
  ...[['overlapping', 1, 1], ['touching', 2, 1], ['disjoint', 3, 1], ['contained', 0, 0.5]].flatMap(([relation, offsetX, scale]) =>
    operations.map(([operation, label]) => ({ name: `${relation[0].toUpperCase()}${relation.slice(1)} cubes ${label}`,
      datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, relation, offsetX, scale, operation,
      output: `math3d-native-${relation}-cubes-${label}.m3dm` }))),
];

export const transform = (mesh, scale = 1, offsetX = 0) => ({
  vertices: mesh.vertices.map(([x, y, z]) => [x * scale + offsetX, y * scale, z * scale]), faces: mesh.faces,
});
const merge = (a, b, reverse = false) => ({ vertices: [...a.vertices, ...b.vertices],
  faces: [...a.faces, ...b.faces.map(face => (reverse ? [...face].reverse() : face).map(index => index + a.vertices.length))] });
const empty = () => ({ vertices: [], faces: [] });

// Independent analytic boundary meshes, not results produced by the native worker.
export function referenceMesh(input, fixture) {
  if (!fixture.relation) return input;
  const right = transform(input, fixture.scale, fixture.offsetX);
  if (fixture.relation === 'disjoint') return fixture.operation === 1 ? merge(input, right) : fixture.operation === 3 ? empty() : input;
  if (fixture.relation === 'contained') return fixture.operation === 1 ? input : fixture.operation === 3 ? right : merge(input, right, true);
  if (fixture.relation === 'touching' && fixture.operation === 3) return empty();
  const min = fixture.operation === 3 ? 0 : -1;
  const max = fixture.operation === 2 ? (fixture.relation === 'touching' ? 1 : 0)
    : fixture.operation === 3 ? 1 : 1 + fixture.offsetX;
  return { vertices: input.vertices.map(([x, y, z]) => [x === 1 ? max : min, y, z]), faces: input.faces };
}
