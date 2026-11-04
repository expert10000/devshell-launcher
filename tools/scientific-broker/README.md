# Scientific Runtime Broker (DS-SCI-021/022)

This is a separate localhost process. It uses the existing version 1 CGAL worker request/result contract and emits the version 1 `math3d.mesh-product-handoff` consumed by `tools/math3d-l9-product-handoff.mjs`. The renderer does not load CGAL or link its SDK.

## Export current certification

Build and run the exporter with five explicit paths:

```powershell
dotnet run --project tools/scientific-broker/ScientificBroker.csproj -- export <devshell-repo> <installed-launcher-root> <math3d-checkout> <profile-id> <manifest.json>
```

The exporter rereads successful runs, verifies fingerprints and immutable qualification files, assesses source, environment, dependency, and MATH3D consumer drift, then exports the newest current L9 CGAL mesh record. If no current L9 record remains, `certifiedCapabilities` is empty. Gmsh and all other unqualified capabilities are excluded. The manifest and its `.sha256` sidecar are a deployment snapshot; export again after qualification or environment changes. The hash detects mismatches, but is not an authenticity signature.

## Configure and run

Create a local JSON file with absolute deployment paths:

```json
{
  "schemaVersion": 1,
  "manifest": "<manifest.json>",
  "runtimeManifest": "<cgal runtime.json>",
  "adapter": "<scientific-cgal-worker.py>",
  "workerContract": "<scientific_worker_contract.py>",
  "python": "<dedicated CGAL python.exe>",
  "worker": "<devshell_cgal_worker.exe>",
  "prefix": "<dedicated CGAL conda prefix>",
  "datasetRoot": "<registered local dataset root>",
  "jobsRoot": "<broker-owned output directory>"
}
```

Deploy the manifest, worker scripts, runtime manifest, environment, and compiled worker at these paths. The broker needs no DevShell desktop process. It verifies their hashes and the conda package inventory when it starts, when it discovers providers, and before each job. The API listens only on `127.0.0.1`; remote transport and authentication are outside this local deployment.

```powershell
python tools/scientific-broker/broker.py verify --config <config.json>
python tools/scientific-broker/broker.py serve --config <config.json> --port 8765
```

## Version 1 API

- `GET /v1/providers`: certified provider and capability discovery.
- `POST /v1/jobs`: accept `schemaVersion`, `runtimeId`, `capabilityId`, `input: {path, sha256}`, and optional `timeoutSeconds` (1–120). The input must be a bounded OBJ inside `datasetRoot` with the exact hash of the qualified L9 fixture.
- `GET /v1/jobs/{id}`: state (`running`, `succeeded`, `partial`, `failed`, `cancelled`, `timed-out`), stage, progress, diagnostics, and verified artifact metadata.
- `POST /v1/jobs/{id}/cancel`: terminate the owned worker process tree.
- `GET /v1/jobs/{id}/artifacts/{name}`: serve only a registered artifact from a successful job after rechecking its hash. Current names are `l5-positive.obj` and `handoff.json`.

Completed job results survive broker restarts. MATH3D can consume `handoff.json` with its existing importer; the handoff pins the worker request, result, output, L8 record, and contract. The broker requires the worker output hash to match the fixed L9 reference artifact. The current implementation covers the qualified CGAL mesh path only. Broader provider discovery and promotion controls belong to later roadmap stages.
