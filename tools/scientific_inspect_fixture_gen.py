"""Regenerate the shared inspection sphere tiers with deterministic vertex order."""
from hashlib import sha256
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'scientific/fixtures/inspect-shared'


def generated(level):
    vertices = [(1., 0., 0.), (-1., 0., 0.), (0., 1., 0.),
                (0., -1., 0.), (0., 0., 1.), (0., 0., -1.)]
    faces = [(4, 0, 2), (4, 2, 1), (4, 1, 3), (4, 3, 0),
             (5, 2, 0), (5, 1, 2), (5, 3, 1), (5, 0, 3)]
    for _ in range(level):
        edges = {}

        def middle(a, b):
            key = tuple(sorted((a, b)))
            if key not in edges:
                point = tuple((vertices[a][i] + vertices[b][i]) / 2 for i in range(3))
                norm = sqrt(sum(value * value for value in point))
                edges[key] = len(vertices)
                vertices.append(tuple(value / norm for value in point))
            return edges[key]

        refined = []
        for a, b, c in faces:
            ab, bc, ca = middle(a, b), middle(b, c), middle(c, a)
            refined.extend(((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)))
        faces = refined
    lines = ['# CC0-1.0 deterministic subdivided octahedron']
    lines += [f'v {x:.12f} {y:.12f} {z:.12f}' for x, y, z in vertices]
    lines += [f'f {a+1} {b+1} {c+1}' for a, b, c in faces]
    return '\n'.join(lines) + '\n', len(vertices), len(faces)


if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    for level in (2, 3, 4):
        value, points, triangles = generated(level)
        path = DEST / f'sphere-{triangles}.obj'
        path.write_text(value, encoding='ascii', newline='\n')
        print(path.relative_to(ROOT), points, triangles, sha256(path.read_bytes()).hexdigest())
