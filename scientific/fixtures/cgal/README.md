# Authored CGAL fixture corpus

These four small OBJ files are project-authored and released under CC0-1.0. `manifest.v1.json` pins their bytes, version and expected independent geometry measurements. The closed tetra is the canonical positive fixture; the other files expose an open boundary, zero-area face and nonmanifold edge. The corpus is for local validation and regression work. It does not extend the fixed broker certification.

`orientation/inward-tetra.obj` is a separately versioned CC0 reversal of the canonical tetrahedron. Its own manifest pins both source and reversed bytes, so the original four-fixture corpus and saved replay reports remain intact.

Run `python tools/scientific_cgal_corpus.py verify` from the repository root to check fixture hashes, rights and geometry. `scientific_cgal_corpus_replay.py run --worker <devshell_cgal_worker.exe> --prefix <CGAL-Conda-prefix> --output-root <local-output>` saves a hash-checked native worker replay. `scientific_cgal_metamorphic.py run` takes the same worker, prefix and output arguments plus `--seed <integer>`; it generates four affine tetrahedra, checks topology and scaled volume, and saves a minimized input if a case fails. Both runners have a `verify --report <saved-report.json>` command. Generated runs belong under ignored `.scientific` paths.
