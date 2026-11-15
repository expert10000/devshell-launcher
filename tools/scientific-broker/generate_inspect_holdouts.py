"""Deterministic icosphere holdouts independent of the registered UV-sphere bases."""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'scientific/fixtures/inspect-classes'


def sphere(level):
    golden = (1 + math.sqrt(5)) / 2
    vertices = [(-1, golden, 0), (1, golden, 0), (-1, -golden, 0), (1, -golden, 0),
                (0, -1, golden), (0, 1, golden), (0, -1, -golden), (0, 1, -golden),
                (golden, 0, -1), (golden, 0, 1), (-golden, 0, -1), (-golden, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
             (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
             (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    vertices = [tuple(value / math.sqrt(sum(part * part for part in point)) for value in point)
                for point in vertices]
    for _ in range(level):
        middle = {}
        def midpoint(a, b):
            key = tuple(sorted((a, b)))
            if key not in middle:
                point = tuple((vertices[a][axis] + vertices[b][axis]) / 2 for axis in range(3))
                length = math.sqrt(sum(value * value for value in point))
                middle[key] = len(vertices)
                vertices.append(tuple(value / length for value in point))
            return middle[key]
        next_faces = []
        for a, b, c in faces:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            next_faces.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
        faces = next_faces
    moved = []
    for x, y, z in vertices:
        radius = 1 + .018 * math.sin(7 * x + 3 * y) * math.cos(5 * z)
        moved.append((.12 + x * radius, -.08 + y * radius, .06 + z * radius))
    return moved, faces


def render(vertices, faces):
    return ''.join('v ' + ' '.join(f'{value:.7f}' for value in point) + '\n' for point in vertices) + \
           ''.join('f ' + ' '.join(str(index + 1) for index in face) + '\n' for face in faces)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for level in (1, 2, 3):
        vertices, faces = sphere(level)
        (DEST / f'ico-{len(faces)}-holdout.obj').write_text(render(vertices, faces), encoding='utf-8')
        if level == 1:
            (DEST / 'ico-open.obj').write_text(render(vertices, faces[:-1]), encoding='utf-8')
            reversed_faces = faces.copy()
            reversed_faces[0] = tuple(reversed(reversed_faces[0]))
            (DEST / 'ico-flipped.obj').write_text(render(vertices, reversed_faces), encoding='utf-8')
            collapsed = vertices.copy()
            collapsed[1] = collapsed[0]
            (DEST / 'ico-collapsed.obj').write_text(render(collapsed, faces), encoding='utf-8')
            remote = [(1.1, 0, 0), (-.9, 0, 0), (0, 1.1, 0), (0, 0, 1.1)]
            remote_faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
            (DEST / 'ico-disconnected.obj').write_text(render(vertices + remote, faces +
                [tuple(index + len(vertices) for index in face) for face in remote_faces]), encoding='utf-8')
            nonfinite = vertices.copy()
            nonfinite[0] = (float('nan'), *vertices[0][1:])
            (DEST / 'ico-nonfinite.obj').write_text(render(nonfinite, faces), encoding='utf-8')
            far = vertices.copy()
            far[0] = tuple(value * 10 for value in far[0])
            (DEST / 'ico-oversize.obj').write_text(render(far, faces), encoding='utf-8')


if __name__ == '__main__':
    main()
