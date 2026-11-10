"""Bounded bidirectional vertex-to-triangle surface displacement measurements."""
import math

from scientific_cgal_mesh_metrics import parse_obj
from scientific_cgal_query_oracle import squared, triangle_closest


def directed_samples(vertices, faces, target_vertices, target_faces):
    if len(vertices) > 4096 or len(target_faces) > 2048:
        raise ValueError('Surface sampling exceeds the comparison budget.')
    triangles = [tuple(target_vertices[index] for index in face) for face in target_faces]
    distances = [math.sqrt(min(squared(point, triangle_closest(point, *triangle))
                               for triangle in triangles)) for point in vertices]
    return {'samples': len(distances), 'maximumDistance': max(distances),
            'meanDistance': sum(distances) / len(distances),
            'rootMeanSquareDistance': math.sqrt(sum(value*value for value in distances)
                                               / len(distances))}


def surface_samples(source, target):
    source_vertices, source_faces = parse_obj(source)
    target_vertices, target_faces = parse_obj(target)
    return {'sourceVerticesToTarget': directed_samples(source_vertices, source_faces,
                                                       target_vertices, target_faces),
            'targetVerticesToSource': directed_samples(target_vertices, target_faces,
                                                       source_vertices, source_faces)}
