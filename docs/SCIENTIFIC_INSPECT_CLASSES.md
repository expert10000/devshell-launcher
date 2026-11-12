# Bounded `mesh.inspect` classes

`schemas/scientific-mesh-inspect-classes.v1.json` defines three deliberately narrow
classes: tetrahedron (4 faces), octahedron (8 faces), and cube (12 faces). Each
requires the base mesh's oriented triangular face indices, a positive uniform
scale from 0.5 through 2, translation of at most 2 units per axis, finite
coordinates, and an OBJ no larger than 64 KiB. Materials, normals, other
records, topology edits, nonuniform scale, reflections, and larger meshes are
outside this versioned scope. A class accepts many hashes; the pinned base and
holdout hashes define and challenge its geometry.

CGAL inspection suite v3 and VTK read suite v4 run independent holdout meshes
through desktop L5–L9. The typed broker `classId` request reclassifies the
input, checks the output's oriented geometry, transports artifacts, and checks
again during promotion. Rejection fixtures cover mirror, nonuniform scale,
overscale, and flipped faces.

After a current six-capability release, run
`python tools/scientific-broker/class_inspect_qualification.py run --release <release.json> --output-root <directory>`.
The record contains five or more randomized paired, promoted broker runs per
provider and class, plus rejection evidence for both providers. `verify
--record <classes.json>` rechecks the release, source, host, desktop L9 IDs,
policy, artifacts, geometry, statistics, resource telemetry, and current broker
promotion. The advisor may admit a class only while this record verifies.
`schemas/scientific-inspect-ranking.v1.json` requires matching paired cold and
warm results, 95% confidence intervals excluding a tie, at least 10% median
advantage, and bounded time and memory. `advisor.py advise-class --class-record
<classes.json> --input <mesh.obj> --output-root <directory>` abstains on close,
inconsistent, stale, or unqualified evidence. Manual provider choice remains
available only within a qualified class. This scope does not claim arbitrary
closed meshes or the larger exact fixture tiers.
