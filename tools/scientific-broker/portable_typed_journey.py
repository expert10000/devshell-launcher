"""Signed, path-free typed journey evidence with an independent offline verifier."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
import zipfile

from portable_six_evidence import (compact, path_free, portable_artifact,
                                   signing_identity, verify as verify_six_bundle,
                                   verify_signature)
from typed_journey_broker import ARTIFACTS, TypedJourneyBroker
from typed_journey_release import DESKTOP_ARTIFACTS, build as build_candidate
from verify_typed_product import verify as verify_product


MAX_MEMBER = 64 * 1024 * 1024
MAX_BUNDLE = 128 * 1024 * 1024
HEX = set('0123456789abcdef')
SOURCE = ('a.obj', 'b.obj', 'boolean.obj')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hash_value(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def permitted(name, data):
    """Preserve evidence bytes; reject local paths, unsafe formats and metadata."""
    if len(data) > MAX_MEMBER:
        raise ValueError('Typed payload exceeds its size budget: ' + name)
    if name.endswith('.json'):
        json.loads(data)
        path_free(data)
    else:
        cleaned, _ = portable_artifact(name, data)
        if cleaned != data:
            raise ValueError('Typed payload contains paths or removable metadata: ' + name)
    return data


def closed_obj(data):
    """Independently check bounded triangular OBJ inputs and outward topology."""
    vertices, faces, edges = [], [], {}
    for line in data.decode('utf-8').splitlines():
        fields = line.strip().split()
        if not fields or fields[0] == '#':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            vertex = tuple(float(value) for value in fields[1:])
            if not all(math.isfinite(value) for value in vertex):
                raise ValueError('Typed source OBJ has nonfinite coordinates.')
            vertices.append(vertex)
        elif fields[0] == 'f' and len(fields) == 4:
            face = tuple(int(value) - 1 for value in fields[1:])
            if min(face) < 0 or max(face) >= len(vertices) or len(set(face)) != 3:
                raise ValueError('Typed source OBJ has invalid triangle indices.')
            faces.append(face)
            for a, b in zip(face, face[1:] + face[:1]):
                key = tuple(sorted((a, b)))
                edges.setdefault(key, []).append((a, b))
        else:
            raise ValueError('Typed source OBJ is outside the bounded triangle policy.')
    if (not vertices or not faces or len(vertices) > 100000 or len(faces) > 200000
            or any(len(use) != 2 or use[0] != use[1][::-1]
                                          for use in edges.values())):
        raise ValueError('Typed source OBJ is not a closed oriented surface.')
    volume = 0.0
    for a, b, c in faces:
        x, y, z = (vertices[index] for index in (a, b, c))
        volume += (x[0] * (y[1] * z[2] - y[2] * z[1])
                   + x[1] * (y[2] * z[0] - y[0] * z[2])
                   + x[2] * (y[0] * z[1] - y[1] * z[0])) / 6
    if volume <= 0:
        raise ValueError('Typed source OBJ has no positive enclosed volume.')
    return {'vertices': len(vertices), 'triangles': len(faces), 'volume': volume}


def stage_relations(root, candidate, source_hashes):
    def record(name, operation, parent):
        value = json.loads((root / name).read_bytes())
        if (value.get('schemaVersion') != 1 or value.get('state') != 'succeeded'
                or value.get('operation') != operation or value.get('sourceRunId') != parent
                or value.get('sourceCommit') != candidate['sourceCommit']):
            raise ValueError('Typed stage identity or parent changed: ' + name)
        return value

    provenance = json.loads((root / 'typed-provenance.json').read_bytes())
    if (provenance.get('sourceCommit') != candidate['sourceCommit']
            or provenance.get('math3dCommit') != candidate['math3dCommit']
            or [provenance.get('booleanSourceASha256'), provenance.get('booleanSourceBSha256'),
                provenance.get('booleanSurfaceSha256')] != source_hashes):
        raise ValueError('Typed Boolean source or consumer lineage changed.')
    parent = candidate['desktop']['sourceRunId']
    gmsh = record('gmsh/results.json', 'gmsh.mesh', parent)
    if (gmsh.get('dimension') != 3 or gmsh.get('inputHashes', {}).get('boolean-surface') != source_hashes[2]
            or gmsh.get('outputHashes', {}).get('gmsh-mesh') != provenance['gmshMeshSha256']
            or gmsh.get('physicalGroups', {}).get('BooleanVolume', {}).get('dimension') != 3
            or gmsh.get('physicalGroups', {}).get('InputBoundary', {}).get('dimension') != 2):
        raise ValueError('Typed Gmsh volume or physical groups changed.')
    boundary = record('boundary/results.json', 'gmsh.extract-boundary', gmsh['runId'])
    if (boundary.get('dimension') != 2 or boundary.get('inputHashes', {}).get('gmsh-mesh') != provenance['gmshMeshSha256']
            or boundary.get('outputHashes', {}).get('gmsh-boundary') != provenance['gmshBoundarySha256']):
        raise ValueError('Typed volume boundary lineage changed.')
    vtk = record('vtk/results.json', 'mesh.inspect', boundary['runId'])
    if (vtk.get('inputHashes', {}).get('gmsh-boundary') != provenance['gmshBoundarySha256']
            or vtk.get('outputHashes', {}).get('vtk-analysis') != provenance['vtkArtifactSha256']):
        raise ValueError('Typed VTK analysis lineage changed.')
    scipy = record('scipy/measurement.json', 'scipy.measure', vtk['runId'])
    if scipy.get('inputHashes', {}).get('vtk-analysis') != provenance['vtkArtifactSha256']:
        raise ValueError('Typed SciPy analysis lineage changed.')
    for value in (gmsh, boundary, vtk):
        if (value.get('lengthUnit') != provenance['lengthUnit']
                or value.get('frame') != provenance['frame']
                or value.get('sourceSnapshotSha256') != provenance['sourceSnapshotSha256']):
            raise ValueError('Typed stage unit, frame or source snapshot changed.')
    if scipy.get('sourceSnapshotSha256') != provenance['sourceSnapshotSha256']:
        raise ValueError('Typed SciPy source snapshot changed.')
    conversion = json.loads((root / 'conversion.json').read_bytes())
    if (conversion.get('sourceArtifactSha256') != provenance['vtkArtifactSha256']
            or conversion.get('objSha256') != provenance['convertedObjSha256']):
        raise ValueError('Typed MATH3D conversion lineage changed.')
    return provenance


def export(release, desktop, broker, broker_config, six_bundle, signing_key, key_id, output, trust_store):
    candidate = build_candidate(release, desktop, broker, broker_config)
    six = verify_six_bundle(six_bundle, trust_store)
    with zipfile.ZipFile(six_bundle) as archive:
        six_manifest = json.loads(archive.read('manifest.json'))
    if (six['signature'] != 'trusted' or six['sourceCommit'] != candidate['sourceCommit']
            or six_manifest['liveRecordSha256'] != candidate['sixReleaseSha256']):
        raise ValueError('Six-capability bundle differs from current journey support.')
    config = json.loads(Path(broker_config).read_text(encoding='utf-8'))
    boolean_path, boolean, surface, _, _ = TypedJourneyBroker(config).verify()
    if boolean['runId'] != candidate['desktop']['sourceRunId']:
        raise ValueError('Portable Boolean parent differs.')
    objects = {}

    def add(name, data, expected):
        if not hash_value(expected) or digest(data) != expected:
            raise ValueError('Portable typed payload changed: ' + name)
        permitted(name, data)
        objects[expected] = data

    source_hashes = [item['sha256'] for item in boolean['inputArtifacts']] + [digest(surface.read_bytes())]
    registered_root = (Path(config['datasetRoot']).resolve(strict=True).parent / 'datasets').resolve(strict=True)
    for name, item in zip(SOURCE[:2], boolean['inputArtifacts']):
        source_path = Path(item['path'])
        path = source_path.resolve(strict=True)
        if source_path.is_symlink() or not path.is_relative_to(registered_root):
            raise ValueError('Portable source mesh escaped the registered dataset root.')
        add(name, path.read_bytes(), item['sha256'])
    add(SOURCE[2], surface.read_bytes(), source_hashes[2])
    for name, expected in candidate['desktop']['artifactHashes'].items():
        add(name, (Path(desktop).parent / name).read_bytes(), expected)
    for alias, expected in candidate['broker']['artifactHashes'].items():
        add(ARTIFACTS[alias], (Path(broker).parent / ARTIFACTS[alias]).read_bytes(), expected)
    candidate_bytes = compact(candidate)
    path_free(candidate_bytes)
    six_bytes = Path(six_bundle).read_bytes()
    if len(six_bytes) > MAX_MEMBER:
        raise ValueError('Signed six-capability bundle exceeds the typed transport budget.')
    manifest = {'schemaVersion': 1, 'kind': 'scientific.portable-typed-journey',
                'sourceCommit': candidate['sourceCommit'], 'math3dCommit': candidate['math3dCommit'],
                'booleanRunId': boolean['runId'], 'sourceHashes': source_hashes,
                'validationHashes': [config['caseProfile']['validationASha256'],
                                     config['caseProfile']['validationBSha256']],
                'candidateSha256': digest(candidate_bytes), 'sixBundleSha256': digest(six_bytes),
                'desktopArtifacts': candidate['desktop']['artifactHashes'],
                'brokerArtifacts': candidate['broker']['artifactHashes'],
                'objects': {key: len(value) for key, value in sorted(objects.items())},
                'signingKeyId': key_id}
    body = compact(manifest)
    path_free(body)
    key = signing_identity(signing_key, key_id)
    signature = compact({'schemaVersion': 1, 'algorithm': 'Ed25519', 'keyId': key_id,
                         'signedAtUtc': datetime.now(timezone.utc).isoformat(),
                         'signatureBase64': base64.b64encode(key.sign(body)).decode('ascii')})
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr('candidate.json', candidate_bytes)
        archive.writestr('support/six-capability.zip', six_bytes)
        for key, data in sorted(objects.items()):
            archive.writestr('objects/sha256/' + key, data)
        archive.writestr('manifest.json', body)
        archive.writestr('manifest.sha256', digest(body))
        archive.writestr('manifest.signature.json', signature)
    return verify(output, trust_store)


def verify(bundle, trust_store):
    bundle = Path(bundle).resolve(strict=True)
    if bundle.stat().st_size > MAX_BUNDLE:
        raise ValueError('Portable typed bundle exceeds the archive budget.')
    with zipfile.ZipFile(bundle) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if (len(names) != len(set(names)) or any(item.is_dir() or item.file_size > MAX_MEMBER
                or item.filename.startswith('/') or '\\' in item.filename or '..' in item.filename.split('/')
                or (item.external_attr >> 16) & 0o170000 == 0o120000 for item in infos)):
            raise ValueError('Portable typed bundle contains unsafe entries.')
        body = archive.read('manifest.json')
        if digest(body) != archive.read('manifest.sha256').decode('ascii'):
            raise ValueError('Portable typed manifest seal changed.')
        manifest = json.loads(body)
        if (manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.portable-typed-journey'
                or compact(manifest) != body):
            raise ValueError('Portable typed manifest contract changed.')
        signature = json.loads(archive.read('manifest.signature.json'))
        if signature.get('keyId') != manifest.get('signingKeyId'):
            raise ValueError('Portable typed signing key changed.')
        verify_signature(body, signature, trust_store)
        objects = manifest['objects']
        if (not isinstance(objects, dict) or len(objects) > 48
                or any(not hash_value(key) or not isinstance(size, int) or size < 0 or size > MAX_MEMBER
                       for key, size in objects.items())):
            raise ValueError('Portable typed object inventory is invalid.')
        expected = {'candidate.json', 'support/six-capability.zip', 'manifest.json',
                    'manifest.sha256', 'manifest.signature.json'} | {'objects/sha256/' + key for key in objects}
        if set(names) != expected:
            raise ValueError('Portable typed archive inventory changed.')
        candidate_bytes = archive.read('candidate.json')
        path_free(candidate_bytes)
        candidate = json.loads(candidate_bytes)
        if (digest(candidate_bytes) != manifest['candidateSha256']
                or candidate['sourceCommit'] != manifest['sourceCommit']
                or candidate['math3dCommit'] != manifest['math3dCommit']
                or candidate['desktop']['sourceRunId'] != manifest['booleanRunId']
                or candidate['broker']['sourceRunId'] != manifest['booleanRunId']
                or candidate['desktop']['sourceCommit'] != manifest['sourceCommit']
                or candidate['broker']['sourceCommit'] != manifest['sourceCommit']
                or candidate['desktop']['consumerCommit'] != manifest['math3dCommit']
                or candidate['broker']['consumerCommit'] != manifest['math3dCommit']
                or candidate['desktop']['artifactHashes'] != manifest['desktopArtifacts']
                or candidate['broker']['artifactHashes'] != manifest['brokerArtifacts']):
            raise ValueError('Portable typed candidate identities changed.')
        if (set(manifest['desktopArtifacts']) != DESKTOP_ARTIFACTS
                or set(manifest['brokerArtifacts']) != set(ARTIFACTS)
                or len(manifest['sourceHashes']) != 3
                or len(set(manifest['sourceHashes'][:2])) != 2
                or any(not hash_value(value) for value in manifest['sourceHashes'] + manifest['validationHashes'])
                or len(manifest['validationHashes']) != 2):
            raise ValueError('Portable typed source or artifact scope changed.')
        referenced = set(manifest['sourceHashes']) | set(manifest['desktopArtifacts'].values()) | set(manifest['brokerArtifacts'].values())
        if referenced != set(objects):
            raise ValueError('Portable typed objects are missing or unreferenced.')
        payloads = {}
        for key, size in objects.items():
            data = archive.read('objects/sha256/' + key)
            if len(data) != size or digest(data) != key:
                raise ValueError('Portable typed object changed: ' + key)
            payloads[key] = data
        for name, key in zip(SOURCE, manifest['sourceHashes']):
            permitted(name, payloads[key])
            closed_obj(payloads[key])
        for name, key in manifest['desktopArtifacts'].items():
            permitted(name, payloads[key])
        for alias, key in manifest['brokerArtifacts'].items():
            permitted(ARTIFACTS[alias], payloads[key])
        six_bytes = archive.read('support/six-capability.zip')
        if digest(six_bytes) != manifest['sixBundleSha256']:
            raise ValueError('Nested six-capability bundle changed.')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        six_path = root / 'six.zip'
        six_path.write_bytes(six_bytes)
        six = verify_six_bundle(six_path, trust_store)
        with zipfile.ZipFile(six_path) as archive:
            six_manifest = json.loads(archive.read('manifest.json'))
        if (six['signature'] != 'trusted' or six['sourceCommit'] != manifest['sourceCommit']
                or six_manifest['liveRecordSha256'] != candidate['sixReleaseSha256']):
            raise ValueError('Nested six-capability support differs from typed candidate.')
        for role, mapping in (('desktop', manifest['desktopArtifacts']),
                              ('broker', {ARTIFACTS[key]: value for key, value in manifest['brokerArtifacts'].items()})):
            folder = root / role
            for name, key in mapping.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payloads[key])
            product = verify_product(folder / 'product', folder / 'typed-provenance.json',
                folder / 'scipy/measurement.json', folder / 'vtk/analysis.vtp',
                folder / 'converted.obj', folder / 'cold-reopen.json')
            if (product['documentId'] != candidate[role]['documentId']
                    or product['sourceCommit'] != manifest['sourceCommit']
                    or product['math3dCommit'] != manifest['math3dCommit']):
                raise ValueError('Offline typed product differs from candidate: ' + role)
        desktop_provenance = stage_relations(root / 'desktop', candidate, manifest['sourceHashes'])
        broker_provenance = json.loads((root / 'broker/typed-provenance.json').read_bytes())
        if (broker_provenance.get('booleanSourceASha256') != manifest['sourceHashes'][0]
                or broker_provenance.get('booleanSourceBSha256') != manifest['sourceHashes'][1]
                or broker_provenance.get('booleanSurfaceSha256') != manifest['sourceHashes'][2]
                or broker_provenance.get('sourceSnapshotSha256') != desktop_provenance['sourceSnapshotSha256']):
            raise ValueError('Desktop and broker Boolean ancestry differs.')
    return {'verdict': 'verified-historical-evidence', 'signature': 'trusted',
            'sourceCommit': manifest['sourceCommit'], 'math3dCommit': manifest['math3dCommit'],
            'booleanRunId': manifest['booleanRunId'], 'payloads': len(objects) + 1,
            'manifestSha256': digest(body)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('export', 'verify'))
    parser.add_argument('--release')
    parser.add_argument('--desktop')
    parser.add_argument('--broker')
    parser.add_argument('--broker-config')
    parser.add_argument('--six-bundle')
    parser.add_argument('--signing-key')
    parser.add_argument('--key-id')
    parser.add_argument('--output')
    parser.add_argument('--bundle')
    parser.add_argument('--trust-store', required=True)
    options = parser.parse_args()
    if options.command == 'export':
        if not all((options.release, options.desktop, options.broker, options.broker_config,
                    options.six_bundle, options.signing_key, options.key_id, options.output)):
            parser.error('export requires release, journeys, broker profile, six bundle, signing key and output')
        report = export(options.release, options.desktop, options.broker, options.broker_config,
                        options.six_bundle, options.signing_key, options.key_id, options.output,
                        options.trust_store)
    else:
        if not options.bundle:
            parser.error('verify requires --bundle')
        report = verify(options.bundle, options.trust_store)
    print(json.dumps(report, sort_keys=True))
