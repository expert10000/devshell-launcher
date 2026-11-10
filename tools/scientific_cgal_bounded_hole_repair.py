"""Native regression for bounded multi-loop CGAL hole filling."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_mesh_metrics import metrics


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ('triangle', 'scientific/fixtures/cgal-repair/tetra-one-hole.obj', 1, 3, 1),
    ('square', 'scientific/fixtures/cgal-repair-quad/cube-one-quad-hole.obj', 1, 4, 2),
    ('two-squares', 'scientific/fixtures/cgal-repair-multi/cube-two-square-holes.obj', 2, 8, 4),
    ('pentagon', 'scientific/fixtures/cgal-repair-bounded/pentagonal-pyramid-open-base.obj', 1, 5, 3),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(worker, prefix, output_root):
    worker, prefix = Path(worker).resolve(strict=True), Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe':
        raise ValueError('Expected the registered hole-repair executable')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'), str(prefix / 'Scripts'), env.get('PATH', '')))
    records = []
    for name, relative, loops, edges, patches in CASES:
        source = ROOT / relative
        before = metrics(source)
        if (before['boundaryLoops'], before['boundaryEdges']) != (loops, edges):
            raise ValueError(name + ': authored input topology changed')
        folder = root / name
        folder.mkdir()
        output = folder / 'repaired.obj'
        process = subprocess.run([str(worker), 'fill-bounded-holes', str(source), str(output)],
                                 cwd=folder, env=env, capture_output=True, text=True, timeout=90)
        (folder / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
        after = metrics(output) if output.is_file() else None
        if (process.returncode != 0 or result['state'] != 'succeeded' or after is None
                or result['boundaryLoopsBefore'] != loops or result['boundaryEdgesBefore'] != edges
                or result['patchFaces'] != patches or result['holesFilled'] != loops
                or result['afterFaces'] != before['faces'] + patches
                or after['faces'] != before['faces'] + patches or after['vertices'] != before['vertices']
                or after['boundaryEdges'] != 0 or after['components'] != 1
                or after['signedVolume'] <= 0):
            raise ValueError(name + ': bounded repair evidence changed')
        records.append({'caseId': name, 'inputSha256': sha(source), 'resultSha256': sha(folder / 'results.json'),
                        'outputSha256': sha(output), 'patchFaceCounts': result['patchFaceCounts'],
                        'signedVolume': after['signedVolume']})
    folder = root / 'closed-rejection'
    folder.mkdir()
    source = ROOT / 'scientific/fixtures/cgal/closed-tetra.obj'
    process = subprocess.run([str(worker), 'fill-bounded-holes', str(source), str(folder / 'refused.obj')],
                             cwd=folder, env=env, capture_output=True, text=True, timeout=90)
    denied = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    if process.returncode == 0 or denied['state'] != 'failed' or (folder / 'refused.obj').exists():
        raise ValueError('Out-of-scope input produced an artifact')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-bounded-hole-repair',
              'workerSha256': sha(worker), 'sourceSha256': sha(ROOT / 'scientific/cgal-worker/hole_repair.cpp'),
              'cases': records, 'rejectionResultSha256': sha(folder / 'results.json'), 'verdict': 'passed'}
    (root / 'bounded-repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(root / 'bounded-repair.json'), 'verdict': 'passed', 'positive': len(records)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    run(args.worker, args.prefix, args.output_root)
