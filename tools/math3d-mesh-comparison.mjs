export function meshStats(mesh) {
  const edges = new Map();
  const neighbors = Array.from({ length: mesh.vertices.length }, () => new Set());
  let signedVolume = 0, area = 0;
  for (const [a, b, c] of mesh.faces) {
    const p = mesh.vertices[a], q = mesh.vertices[b], r = mesh.vertices[c];
    const cross = [(q[1] - p[1]) * (r[2] - p[2]) - (q[2] - p[2]) * (r[1] - p[1]),
      (q[2] - p[2]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[2] - p[2]),
      (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])];
    area += Math.hypot(...cross) / 2;
    signedVolume += (p[0] * (q[1] * r[2] - q[2] * r[1]) +
      p[1] * (q[2] * r[0] - q[0] * r[2]) + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6;
    for (const [u, v] of [[a, b], [b, c], [c, a]]) {
      const key = `${Math.min(u, v)}:${Math.max(u, v)}`;
      const edge = edges.get(key) || { count: 0, direction: 0 };
      edge.count += 1;
      edge.direction += u < v ? 1 : -1;
      edges.set(key, edge);
      neighbors[u].add(v); neighbors[v].add(u);
    }
  }
  const boundaryEdges = [...edges.values()].filter(edge => edge.count === 1).length;
  const nonManifoldEdges = [...edges.values()].filter(edge => edge.count > 2).length;
  const orientationConflicts = [...edges.values()].filter(edge => edge.count === 2 && edge.direction !== 0).length;
  const used = new Set(mesh.faces.flat());
  const visited = new Set();
  let components = 0;
  for (const vertex of used) {
    if (visited.has(vertex)) continue;
    components += 1;
    const pending = [vertex]; visited.add(vertex);
    while (pending.length) for (const adjacent of neighbors[pending.pop()])
      if (!visited.has(adjacent)) { visited.add(adjacent); pending.push(adjacent); }
  }
  const bounds = mesh.vertices.length ? [Infinity, -Infinity, Infinity, -Infinity, Infinity, -Infinity] : null;
  if (bounds) for (const vertex of mesh.vertices) for (let axis = 0; axis < 3; axis++) {
    bounds[axis * 2] = Math.min(bounds[axis * 2], vertex[axis]);
    bounds[axis * 2 + 1] = Math.max(bounds[axis * 2 + 1], vertex[axis]);
  }
  return { vertices: mesh.vertices.length, edges: edges.size, faces: mesh.faces.length,
    boundaryEdges, nonManifoldEdges, orientationConflicts, components,
    euler: used.size - edges.size + mesh.faces.length,
    closed: boundaryEdges === 0 && nonManifoldEdges === 0 && orientationConflicts === 0 && mesh.faces.length > 0,
    bounds, area, signedVolume, volume: Math.abs(signedVolume) };
}

const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
const sub = (a, b) => a.map((value, index) => value - b[index]);
const distanceToSegment = (point, a, b) => {
  const ab = sub(b, a), lengthSquared = dot(ab, ab);
  const t = lengthSquared ? Math.max(0, Math.min(1, dot(sub(point, a), ab) / lengthSquared)) : 0;
  return Math.hypot(...sub(point, a.map((value, index) => value + t * ab[index])));
};

function distanceToTriangle(point, a, b, c) {
  const ab = sub(b, a), ac = sub(c, a), ap = sub(point, a);
  const normal = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]];
  const normalSquared = dot(normal, normal);
  const d00 = dot(ab, ab), d01 = dot(ab, ac), d11 = dot(ac, ac);
  const d20 = dot(ap, ab), d21 = dot(ap, ac), denominator = d00 * d11 - d01 * d01;
  if (normalSquared > 0 && denominator > 0) {
    const v = (d11 * d20 - d01 * d21) / denominator;
    const w = (d00 * d21 - d01 * d20) / denominator;
    if (v >= -1e-12 && w >= -1e-12 && v + w <= 1 + 1e-12)
      return Math.abs(dot(ap, normal)) / Math.sqrt(normalSquared);
  }
  return Math.min(distanceToSegment(point, a, b), distanceToSegment(point, b, c), distanceToSegment(point, c, a));
}

function surfaceSamples(mesh) {
  const samples = [...mesh.vertices];
  const edges = new Set();
  for (const face of mesh.faces) {
    const points = face.map(index => mesh.vertices[index]);
    samples.push([0, 1, 2].map(axis => points.reduce((sum, point) => sum + point[axis], 0) / 3));
    for (const [a, b] of [[0, 1], [1, 2], [2, 0]]) {
      const key = `${Math.min(face[a], face[b])}:${Math.max(face[a], face[b])}`;
      if (edges.has(key)) continue;
      edges.add(key);
      samples.push(points[a].map((value, axis) => (value + points[b][axis]) / 2));
    }
  }
  return samples;
}

function directedSurfaceDeviation(source, target) {
  if (!source.faces.length) return target.faces.length ? Infinity : 0;
  if (!target.faces.length) return Infinity;
  return Math.max(...surfaceSamples(source).map(point => Math.min(...target.faces.map(face =>
    distanceToTriangle(point, ...face.map(index => target.vertices[index]))))));
}

export function numericComparison(input, output, before, after) {
  if (!output || !after) return null;
  const scale = Math.max(1, ...(before.bounds ? [before.bounds[1] - before.bounds[0], before.bounds[3] - before.bounds[2], before.bounds[5] - before.bounds[4]] : []));
  return {
    metrics: {
      boundsDelta: before.bounds && after.bounds ? Math.max(...before.bounds.map((value, index) => Math.abs(value - after.bounds[index]))) : before.bounds === after.bounds ? 0 : Infinity,
      areaDelta: Math.abs(before.area - after.area), volumeDelta: Math.abs(before.volume - after.volume),
      sampledSurfaceDeviation: Math.max(directedSurfaceDeviation(input, output), directedSurfaceDeviation(output, input)),
      triangleCountDelta: after.faces - before.faces,
    },
    tolerances: { bounds: 1e-5 * scale, area: 1e-5 * scale ** 2,
      volume: 1e-5 * scale ** 3, sampledSurface: 1e-5 * scale },
  };
}
