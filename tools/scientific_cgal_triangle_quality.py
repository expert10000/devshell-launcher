"""Independent, scale-invariant triangle shape measurements for bounded OBJs."""
import math

from scientific_cgal_mesh_metrics import parse_obj


def triangle_quality(a, b, c):
    lengths = (math.dist(b, c), math.dist(a, c), math.dist(a, b))
    if min(lengths) <= 0:
        raise ValueError('Triangle quality requires positive edge lengths.')
    squares = [length * length for length in lengths]
    angles = [math.degrees(math.acos(max(-1.0, min(1.0,
              (squares[(index + 1) % 3] + squares[(index + 2) % 3] - squares[index])
              / (2 * lengths[(index + 1) % 3] * lengths[(index + 2) % 3])))))
              for index in range(3)]
    ab = [b[index] - a[index] for index in range(3)]
    ac = [c[index] - a[index] for index in range(3)]
    cross = (ab[1]*ac[2] - ab[2]*ac[1], ab[2]*ac[0] - ab[0]*ac[2],
             ab[0]*ac[1] - ab[1]*ac[0])
    twice_area = math.sqrt(sum(value * value for value in cross))
    if twice_area <= 1e-12:
        raise ValueError('Triangle quality rejects degenerate faces.')
    # Equilateral triangles score 1; the score approaches 0 for slivers.
    shape = 2 * math.sqrt(3) * twice_area / sum(squares)
    return min(angles), max(angles), shape


def quality(path):
    vertices, faces = parse_obj(path)
    measured = [triangle_quality(*(vertices[index] for index in face)) for face in faces]
    return {'faces': len(faces),
            'minimumAngleDegrees': min(item[0] for item in measured),
            'maximumAngleDegrees': max(item[1] for item in measured),
            'minimumShapeScore': min(item[2] for item in measured),
            'meanShapeScore': sum(item[2] for item in measured) / len(measured)}
