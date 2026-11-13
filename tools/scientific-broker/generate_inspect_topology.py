"""Generate deterministic independent nonconvex and torus inspection fixtures."""
import math
from pathlib import Path

from generate_inspect_holdouts import render, sphere
from inspect_classes import mesh

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'scientific/fixtures/inspect-topology'


def dimple(vertices, depth):
    center = tuple(sum(point[axis] for point in vertices) / len(vertices) for axis in range(3))
    top = max(point[2] - center[2] for point in vertices)
    changed = []
    for point in vertices:
        height = (point[2] - center[2]) / top
        reduction = depth * (max(0, (height - .48) / .52) ** 2)
        changed.append(tuple(center[axis] + (point[axis] - center[axis]) * (1 - reduction)
                             for axis in range(3)))
    return changed


def torus(u_count, v_count, diagonal, major, minor, offset, phase_u, phase_v):
    vertices = []
    for i in range(u_count):
        u = phase_u + 2 * math.pi * i / u_count
        for j in range(v_count):
            v = phase_v + 2 * math.pi * j / v_count
            radius = major + minor * math.cos(v)
            vertices.append((offset[0] + radius * math.cos(u),
                             offset[1] + radius * math.sin(u),
                             offset[2] + minor * math.sin(v)))
    faces = []
    for i in range(u_count):
        for j in range(v_count):
            a = i * v_count + j
            b = ((i + 1) % u_count) * v_count + j
            c = ((i + 1) % u_count) * v_count + (j + 1) % v_count
            d = i * v_count + (j + 1) % v_count
            faces.extend(((a, b, c), (a, c, d)) if diagonal == 0
                         else ((a, b, d), (b, c, d)))
    return vertices, faces


def fixtures():
    uv_vertices, uv_faces = mesh(ROOT / 'scientific/fixtures/inspect-shared/sphere-512.obj')
    ico_vertices, ico_faces = sphere(2)
    result = {
        'scientific/fixtures/inspect-topology/concave-uv-512.obj':
            render(dimple(uv_vertices, .38), uv_faces),
        'scientific/fixtures/inspect-topology/concave-ico-320-holdout.obj':
            render(dimple(ico_vertices, .38), ico_faces),
        'scientific/fixtures/inspect-topology/torus-grid-256.obj':
            render(*torus(16, 8, 0, 1.0, .38, (0., 0., 0.), .15, .1)),
    }
    holdout = torus(20, 10, 1, 1.05, .36, (.06, -.04, .03), .33, .22)
    result['scientific/fixtures/inspect-topology/torus-grid-400-holdout.obj'] = render(*holdout)
    vertices, faces = holdout
    flipped = faces.copy()
    flipped[0] = tuple(reversed(flipped[0]))
    result['scientific/fixtures/inspect-topology/torus-flipped.obj'] = render(vertices, flipped)
    scrambled = vertices.copy()
    scrambled[3], scrambled[80] = scrambled[80], scrambled[3]
    result['scientific/fixtures/inspect-topology/torus-scrambled.obj'] = render(scrambled, faces)
    return result


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for relative, contents in fixtures().items():
        (ROOT / relative).write_text(contents, encoding='utf-8')


if __name__ == '__main__':
    main()
