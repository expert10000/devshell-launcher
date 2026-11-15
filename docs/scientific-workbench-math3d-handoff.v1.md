# Workbench to MATH3D saved-result handoff v1

The managed `workbench-math3d-handoff` action is available only for CGAL and VTK saved Workbench results. It accepts a successful run and one registered OBJ or VTP output. The native boundary verifies the run fingerprint, Git source snapshot, selected artifact hash, current source state, clean pulled MATH3D commit, and renderer dependencies before starting a new owned job. Stale, failed, cancelled, or tampered source runs cannot produce a handoff.

The VTK converter reads the artifact within 32 MiB, accepts only triangular finite geometry within 200,000 points and 400,000 triangles, and writes a bounded OBJ with its own conversion record. The MATH3D consumer imports that OBJ through `loadSurfaceMeshFromFile`, stores the DevShell run, artifact, conversion, catalog and MATH3D commit identity in the Mesh document source, saves the document and binary resource, restores the document, writes M3DM, and decodes it again. `verify_workbench_handoff.py` independently checks the source and output hashes, consumer source files, document provenance, M3DM header, and triangle index bounds.

The action does not promote new capability levels. Its saved result and outputs appear in History. The separate Gmsh surface/volume Workbench contract is still required before Gmsh is offered in this operation catalog.

Before committing this slice, a local conversion of a four-triangle VTP and the pulled `19484d0d` MATH3D consumer completed the document/resource/M3DM reload. The managed final-HEAD desktop run and independent verifier are the release acceptance gate.
