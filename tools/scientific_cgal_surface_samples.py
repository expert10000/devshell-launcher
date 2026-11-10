"""Bounded bidirectional vertex and facet-sample surface displacement."""
import math

from scientific_cgal_mesh_metrics import parse_obj
from scientific_cgal_query_oracle import squared, triangle_closest


def facet_points(vertices, faces):
    if len(vertices) > 4096 or len(faces) > 2048:
        raise ValueError('Surface sampling exceeds the comparison budget.')
    edges = {tuple(sorted((face[index], face[(index + 1) % 3])))
             for face in faces for index in range(3)}
    points = [tuple((vertices[a][axis] + vertices[b][axis]) / 2 for axis in range(3))
              for a, b in sorted(edges)]
    points.extend(tuple(sum(vertices[index][axis] for index in face) / 3 for axis in range(3))
                  for face in faces)
    return points


def directed_samples(points, target_vertices, target_faces):
    if not points or len(points) > 16384 or len(target_faces) > 2048:
        raise ValueError('Surface sampling exceeds the comparison budget.')
    triangles = [tuple(target_vertices[index] for index in face) for face in target_faces]
    distances = [math.sqrt(min(squared(point, triangle_closest(point, *triangle))
                               for triangle in triangles)) for point in points]
    return {'samples': len(distances), 'maximumDistance': max(distances),
            'meanDistance': sum(distances) / len(distances),
            'rootMeanSquareDistance': math.sqrt(sum(value*value for value in distances)
                                               / len(distances))}


def surface_samples(source, target):
    source_vertices, source_faces = parse_obj(source)
    target_vertices, target_faces = parse_obj(target)
    return {'sourceVerticesToTarget': directed_samples(source_vertices,
                                                       target_vertices, target_faces),
            'targetVerticesToSource': directed_samples(target_vertices,
                                                       source_vertices, source_faces),
            'sourceFacetSamplesToTarget': directed_samples(facet_points(source_vertices, source_faces),
                                                           target_vertices, target_faces),
            'targetFacetSamplesToSource': directed_samples(facet_points(target_vertices, target_faces),
                                                           source_vertices, source_faces)}
