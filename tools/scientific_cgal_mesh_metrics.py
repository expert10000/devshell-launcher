"""Independent bounded OBJ metrics for CGAL remeshing evidence."""
from collections import Counter, defaultdict
import math
from pathlib import Path


def parse_obj(path):
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('OBJ mesh exceeds the 32 MiB analysis budget.')
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0] == '#':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            point = tuple(float(value) for value in fields[1:])
            if not all(math.isfinite(value) for value in point):
                raise ValueError('OBJ contains non-finite coordinates.')
            vertices.append(point)
        elif fields[0] == 'f' and len(fields) == 4:
            face = tuple(int(value)-1 for value in fields[1:])
            if len(set(face)) != 3 or any(index < 0 or index >= len(vertices) for index in face):
                raise ValueError('OBJ contains an invalid triangle index.')
            faces.append(face)
        else:
            raise ValueError('OBJ uses an unsupported directive.')
    if not vertices or not faces or len(vertices) > 200000 or len(faces) > 200000:
        raise ValueError('OBJ geometry is empty or over the analysis budget.')
    return vertices, faces


def edge_data(vertices, faces):
    counts = Counter(tuple(sorted((face[index], face[(index+1) % 3])))
                     for face in faces for index in range(3))
    lengths = {edge: math.dist(vertices[edge[0]], vertices[edge[1]]) for edge in counts}
    return counts, lengths


def components(faces, edges):
    owner = defaultdict(list)
    for index, face in enumerate(faces):
        for offset in range(3):
            owner[tuple(sorted((face[offset], face[(offset+1) % 3])))].append(index)
    adjacent = [set() for _ in faces]
    for indices in owner.values():
        for index in indices:
            adjacent[index].update(other for other in indices if other != index)
    visited, count = set(), 0
    for index in range(len(faces)):
        if index in visited:
            continue
        count += 1
        stack = [index]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacent[current] - visited)
    return count


def boundary_loops(boundary):
    if not boundary:
        return 0
    adjacent = defaultdict(set)
    for a, b in boundary:
        adjacent[a].add(b)
        adjacent[b].add(a)
    if any(len(neighbors) != 2 for neighbors in adjacent.values()):
        raise ValueError('Boundary is not a union of closed loops.')
    visited, count = set(), 0
    for start in adjacent:
        if start in visited:
            continue
        count += 1
        stack = [start]
        while stack:
            vertex = stack.pop()
            if vertex in visited:
                continue
            visited.add(vertex)
            stack.extend(adjacent[vertex] - visited)
    return count


def metrics(path):
    vertices, faces = parse_obj(path)
    counts, lengths = edge_data(vertices, faces)
    boundary = [edge for edge, count in counts.items() if count == 1]
    area, volume, degenerate = 0.0, 0.0, 0
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        ab = tuple(b[index]-a[index] for index in range(3))
        ac = tuple(c[index]-a[index] for index in range(3))
        cross = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2],
                 ab[0]*ac[1]-ab[1]*ac[0])
        twice_area = math.sqrt(sum(value*value for value in cross))
        area += twice_area / 2
        if twice_area <= 1e-12:
            degenerate += 1
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1])
                   + a[1]*(b[2]*c[0]-b[0]*c[2])
                   + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
    return {'vertices': len(vertices), 'faces': len(faces), 'edges': len(counts),
            'components': components(faces, counts),
            'boundaryEdges': len(boundary), 'boundaryLoops': boundary_loops(boundary),
            'boundaryLength': sum(lengths[edge] for edge in boundary),
            'maximumEdgeIncidence': max(counts.values()),
            'minimumEdgeLength': min(lengths.values()), 'maximumEdgeLength': max(lengths.values()),
            'degenerateFaces': degenerate, 'area': area, 'signedVolume': volume,
            'eulerCharacteristic': len(vertices)-len(counts)+len(faces),
            'bounds': [[min(point[index] for point in vertices), max(point[index] for point in vertices)]
                       for index in range(3)]}
