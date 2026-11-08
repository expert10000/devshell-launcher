# Standalone CGAL mesh workers

`devshell_cgal_worker` remains the existing validation/remeshing executable. `devshell_cgal_query` is a separate bounded point-to-triangle-mesh AABB query tool. It accepts a triangle OBJ and three finite coordinates within ±1,000,000, rejects degenerate and nonmanifold input, and writes a new `results.json` in its working directory. Distance is unsigned distance to the surface; it does not classify inside versus outside or certify a repair operation.

Build with the installed CGAL CMake package, for example `cmake -S scientific/cgal-worker -B <build-dir> -DCGAL_DIR=<CGAL-prefix>/Library/lib/cmake/CGAL` followed by `cmake --build <build-dir> --config Release --target devshell_cgal_query`. Run the query in a fresh directory with the CGAL Conda prefix and `Library/bin` on `PATH`.

`python tools/scientific_cgal_query.py run --worker <devshell_cgal_query.exe> --prefix <CGAL-prefix> --output-root <local-output>` checks five fixed distances and four expected rejections against the authored corpus. `scientific_cgal_query_metamorphic.py run` uses the same arguments plus `--seed <integer>` to check eight affine distance relations. `scientific_cgal_query_oracle.py run --source-report <fixed-or-metamorphic-report.json> --output-root <local-output>` independently computes point-to-triangle distances and verifies each native closest point lies on a triangle. Each suite has `verify --report <saved-report.json>`.

These are local laboratory checks. The AABB query is not declared as a managed desktop capability and is absent from the certified Scientific Broker manifest.
