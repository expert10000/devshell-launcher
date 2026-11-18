# Portable typed journey evidence

`tools/scientific-broker/portable_typed_journey.py` publishes one signed ZIP only after the local release gate verifies current six-capability support and one desktop and broker journey from the same saved Boolean run. The ZIP includes the already signed six-capability bundle, two registered OBJ inputs, the Boolean OBJ, all 17 managed desktop artifacts, all 13 broker artifacts, and a path-free candidate record. Duplicate payloads are stored once by SHA-256. Source snapshots and broker profile paths stay local; their content hashes and source, consumer, and Boolean identities remain in the signed manifest.

The format policy permits bounded UTF-8 JSON, OBJ, MSH, and VTP, reviewed PNG without metadata, and versioned MATH3D binary payloads. It rejects absolute local paths, unknown archive entries, duplicate members, symlinks, oversized members, unreferenced payloads, and changed content. The offline verifier checks the trusted Ed25519 signature and nested six-capability signature, all object hashes, independently closed and outward source topology, exact Gmsh → boundary → VTK → SciPy parent and artifact hashes, units, frame, generations, product document and resource identity, and a separate-process cold reopen. It needs only the ZIP, verifier, and public trust store; it does not read a worktree, installed app, or private signing key.

After the final merged-HEAD six-capability publication and typed desktop/broker jobs, run:

```text
python tools/scientific-broker/portable_typed_journey.py export --release RELEASE.json --desktop DESKTOP/results.json --broker BROKER/broker-result.json --broker-config PROFILE.json --six-bundle SIX.zip --signing-key PRIVATE.pem --key-id devshell-typed-2026-11 --output TYPED.zip --trust-store schemas/scientific-evidence-trust.v1.json
python tools/scientific-broker/portable_typed_journey.py verify --bundle TYPED.zip --trust-store schemas/scientific-evidence-trust.v1.json
```

The `devshell-typed-2026-11` public key is in the trust store. Its private key must remain outside Git and synchronized folders with access restricted to the release operator. Rotate by adding a new public key ID before first use, retaining older public keys for historical verification. A compromised key receives `revokedAtUtc`; the verifier then rejects all bundles signed with it. A verified portable bundle records historical evidence for its exact source and consumer commits; current support still requires the local source and installed product to match those commits.
