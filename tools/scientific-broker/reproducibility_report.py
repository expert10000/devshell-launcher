"""Sealed, human-readable report from independently verified scientific evidence."""
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import uuid

from broker import Broker, sha
from adapter_conformance import verify_record
from contract_migration import verify as verify_contract
from differential import compare_descriptors, load_saved_mesh, PARSER
from environment_manifest import verify_manifest, verify_recreation
from provenance import verify as verify_provenance
from release_matrix import verify_matrix, verify_snapshot

DEFAULT_POLICY = Path(__file__).resolve().parents[2] / 'schemas' / 'scientific-contract-migrations.v1.json'
SOURCE_NAMES = ('matrix', 'conformance', 'contract', 'environment', 'recreation', 'provenance', 'differential')


def verify_differential(path):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    if (report.get('schemaVersion') != 1 or report.get('suiteId') != 'scientific-differential-v1'
            or report.get('comparatorSha256') != sha(Path(__file__).with_name('differential.py'))
            or report.get('meshParserSha256') != sha(PARSER)):
        raise ValueError('Differential suite or parser changed.')
    descriptors = []
    for side in ('left', 'right'):
        saved = report[side]
        if saved.get('kind') != 'mesh':
            raise ValueError('This report requires saved mesh-run differential evidence.')
        result = Path(saved['sourceResultPath'])
        if sha(result) != saved['sourceResultSha256']:
            raise ValueError('Differential source result changed.')
        artifact = Path(saved['artifactPath'])
        rebuilt = load_saved_mesh(result, artifact.relative_to(result.parent).as_posix())
        if rebuilt != saved:
            raise ValueError('Differential source run fingerprint or artifact changed.')
        descriptors.append(rebuilt)
    tolerance = report['comparison'].get('tolerance')
    if not isinstance(tolerance, (int, float)) or not 0 < tolerance <= 0.01:
        raise ValueError('Invalid differential tolerance.')
    if compare_descriptors(*descriptors, tolerance) != report['comparison']:
        raise ValueError('Differential comparison changed.')
    return report


def load_sources(paths, config, policy):
    matrix = verify_matrix(paths['matrix'])
    snapshots = [verify_snapshot(matrix[side + 'SnapshotPath']) for side in ('left', 'right')]
    conformance = verify_record(paths['conformance'])
    contract = verify_contract(paths['contract'], policy)
    environment = verify_manifest(paths['environment'])
    recreation = verify_recreation(paths['recreation'], paths['environment'])
    provenance = verify_provenance(paths['provenance'], config)
    differential = verify_differential(paths['differential'])
    return matrix, snapshots, conformance, contract, environment, recreation, provenance, differential


def clean(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def render(paths, sources):
    matrix, snapshots, conformance, contract, environment, recreation, provenance, differential = sources
    left, right = snapshots
    smoke_node = provenance['nodes'][-1]
    comparison = differential['comparison']
    broker = Broker(paths['config'])
    manifest_path = broker.paths['manifest']
    if sha(manifest_path) != provenance['manifestSha256']:
        raise ValueError('Historical broker manifest changed.')
    historical = json.loads(manifest_path.read_text(encoding='utf-8'))
    capability = next((item['capabilityId'] for item in historical['certifiedCapabilities']
                       if item['recordId'] == provenance['nodes'][5]['certificationRecordId']), None)
    if not capability:
        raise ValueError('Provenance certification is absent from the historical broker manifest.')
    lines = [
        '# Scientific reproducibility report', '',
        f"Release comparison: **{clean(matrix['leftReleaseTag'])} → {clean(matrix['rightReleaseTag'])}**.",
        f"Overall verdict: **{clean(matrix['verdict'])}**. This is an evidence comparison, not a measured scientific regression.", '',
        '## Capabilities and release gates', '',
        '| Provider | Current qualified capability | Left version | Right version | Left levels | Right levels | Verdict | Confidence |',
        '|---|---|---|---|---:|---:|---|---|',
    ]
    for row, snapshot_row in zip(matrix['rows'], right['rows']):
        lines.append('| ' + ' | '.join(clean(x) for x in (
            row['provider'], ', '.join(snapshot_row['qualifiedCapabilities']) or 'none',
            row['leftVersion'] or 'unknown', row['rightVersion'] or 'unknown',
            row['leftCoverage']['currentLevels'], row['rightCoverage']['currentLevels'],
            row['verdict'], row['confidence'])) + ' |')
    lines += ['', f"- Left release gate: **{clean(left['releaseVerdict'])}**; inventory **{clean(left['inventoryState'])}**; reasons: {clean('; '.join(left['releaseReasons']) or 'none')}",
              f"- Right release gate: **{clean(right['releaseVerdict'])}**; inventory **{clean(right['inventoryState'])}**; reasons: {clean('; '.join(right['releaseReasons']) or 'none')}",
              '- No provider is release certified by a blocked report. Gmsh remains unqualified.', '',
              f"- Historical fixed broker capability: `{clean(capability)}` on CGAL, exercised by source job `{provenance['sourceJobId']}`. It is not current release qualification.", '',
              '## Supporting gate verdicts', '',
              f"- Contract migration: **{clean(contract['verdict'])}**, {len(contract['contracts'])} scoped contract(s).",
              f"- CGAL environment recreation: **{clean(recreation['state'])}**; sandbox removed: {clean(recreation['sandboxRemoved'])}.",
              f"- Saved mesh differential: **{clean(comparison['verdict'])}**; checks: " + ', '.join(f'{clean(k)}={clean(v)}' for k, v in comparison['checks'].items()) + '.',
              '- Adapter conformance is diagnostic evidence and grants no L0–L9 level:', '',
              '| Provider | Conformance | Cases |', '|---|---|---|']
    for provider in conformance['providers']:
        cases = ', '.join(f"{clean(k)}: {clean(v['state'])}" for k, v in provider['cases'].items())
        lines.append(f"| {clean(provider['runtimeId'])} | {clean(provider['verdict'])} | {cases} |")
    lines += ['', '## Fixtures and artifacts', '',
              f"- Exact input: `x²−1`; Sage derivation SHA-256 `{provenance['nodes'][1]['sha256']}`.",
              f"- Fixed tetrahedron OBJ SHA-256 `{provenance['nodes'][4]['sha256']}`; CGAL output SHA-256 `{provenance['nodes'][5]['sha256']}`.",
              f"- MATH3D document SHA-256 `{smoke_node['sha256']}`; source job `{provenance['sourceJobId']}`.",
              f"- Environment lock: {environment['packageCount']} packages; identity SHA-256 `{environment['packageIdentitySha256']}`.",
              f"- Differential inputs: `{differential['left']['artifactSha256']}` and `{differential['right']['artifactSha256']}`.", '',
              '## Fingerprints and tolerances', '',
              f"- Conformance host fingerprint: `{conformance['hostFingerprintSha256']}`; suite revision: `{conformance['suiteRevisionSha256']}`.",
              f"- Runtime manifest SHA-256: `{environment['sourceRuntimeManifestSha256']}`; Python SHA-256: `{environment['sourcePythonSha256']}`.",
              f"- Broker certified manifest SHA-256 in the fixed provenance run: `{provenance['manifestSha256']}`. This historical manifest does not override the blocked release gate.",
              f"- Differential run fingerprints: `{differential['left'].get('runFingerprintSha256', 'unavailable')}` and `{differential['right'].get('runFingerprintSha256', 'unavailable')}`.",
              f"- Differential contract fingerprints: `{differential['left'].get('contractFingerprintSha256', 'unavailable')}` and `{differential['right'].get('contractFingerprintSha256', 'unavailable')}`.",
              f"- Mesh tolerance: `{comparison['tolerance']}` relative/scale-aware according to the bounded surface comparator; comparator SHA-256 `{differential['comparatorSha256']}`.",
              '- Field comparison default: `1e-9` for numeric values; exact rational/polynomial results compare canonically with no numeric tolerance. No field or exact differential run is asserted here.', '',
              '## Regressions and scope', '',
              f"- Product smoke and viewer regression: **passed** in verified source job `{provenance['sourceJobId']}`; viewer regression SHA-256 `{smoke_node['viewerRegressionSha256']}`; independent `.m3dm` reload passed.",
              '- Release comparison is inconclusive; no scientific regression is inferred from version changes or missing evidence.',
              '- Reviewed failure replay fixtures: none supplied to this report.', '',
              '## Reproduce and verify', '',
              'Run these commands from the repository root. Paths below identify the saved local evidence; a fresh qualification requires new runs and inventory.', '',
              '```powershell',
              f"python tools/scientific-broker/release_matrix.py verify --record \"{paths['matrix']}\"",
              f"python tools/scientific-broker/adapter_conformance.py --verify \"{paths['conformance']}\"",
              f"python tools/scientific-broker/contract_migration.py verify --policy \"{paths['policy']}\" --record \"{paths['contract']}\"",
              f"python tools/scientific-broker/environment_manifest.py verify-recreation --manifest \"{paths['environment']}\" --record \"{paths['recreation']}\"",
              f"python tools/scientific-broker/provenance.py verify --config \"{paths['config']}\" --record \"{paths['provenance']}\"",
              f"python tools/scientific-broker/reproducibility_report.py verify --record \"{paths['report']}\"",
              '```', '',
              'To recreate the fixed product path, run `provenance.py build` with the same broker config, then capture a fresh release report and inventory before comparing release qualification.', '',
              '## Source evidence', '']
    for name in SOURCE_NAMES:
        lines.append(f"- {name}: `{paths[name]}`")
    lines.append('')
    return '\n'.join(lines)


def render_html(markdown):
    """Render the report's limited Markdown vocabulary without raw HTML injection."""
    def inline(value):
        value = html.escape(value)
        value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
        return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)

    body, lines, index = [], markdown.splitlines(), 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line == '```powershell':
            end = lines.index('```', index + 1)
            body.append('<pre><code>' + html.escape('\n'.join(lines[index + 1:end])) + '</code></pre>')
            index = end + 1
            continue
        if line.startswith('# '):
            body.append('<h1>' + inline(line[2:]) + '</h1>')
        elif line.startswith('## '):
            body.append('<h2>' + inline(line[3:]) + '</h2>')
        elif line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].startswith('|'):
                rows.append([cell.strip() for cell in lines[index].strip('|').split('|')])
                index += 1
            body.append('<table><thead><tr>' + ''.join('<th>' + inline(cell) + '</th>' for cell in rows[0]) + '</tr></thead><tbody>')
            for row in rows[2:]:
                body.append('<tr>' + ''.join('<td>' + inline(cell) + '</td>' for cell in row) + '</tr>')
            body.append('</tbody></table>')
            continue
        elif line.startswith('- '):
            body.append('<ul>')
            while index < len(lines) and lines[index].startswith('- '):
                body.append('<li>' + inline(lines[index][2:]) + '</li>')
                index += 1
            body.append('</ul>')
            continue
        else:
            body.append('<p>' + inline(line) + '</p>')
        index += 1
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<title>Scientific reproducibility report</title><style>'
            'body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17202a}'
            'table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid #ccd;padding:.5rem;text-align:left}'
            'th{background:#eef}tr:nth-child(even){background:#f8f9fc}pre{overflow:auto;background:#f4f4f4;padding:1rem}'
            'code{overflow-wrap:anywhere}li{margin:.35rem 0}</style><main>' + '\n'.join(body) + '</main></html>\n')


def generate(paths, output_root):
    paths = {name: str(Path(value).resolve(strict=True)) for name, value in paths.items()}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex
    paths['report'] = str(root / (stem + '.json'))
    sources = load_sources(paths, paths['config'], paths['policy'])
    markdown = render(paths, sources)
    md_path, html_path = root / (stem + '.md'), root / (stem + '.html')
    md_path.write_text(markdown, encoding='utf-8')
    html_path.write_text(render_html(markdown), encoding='utf-8')
    record = {'schemaVersion': 1, 'kind': 'scientific.reproducibility-report',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'generatorSha256': sha(Path(__file__)), 'sources': {name: {'path': paths[name], 'sha256': sha(paths[name])}
                                                               for name in SOURCE_NAMES + ('config', 'policy')},
              'markdownSha256': sha(md_path), 'htmlSha256': sha(html_path),
              'releaseVerdict': sources[0]['verdict']}
    report_path = Path(paths['report'])
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    Path(str(report_path) + '.sha256').write_text(sha(report_path), encoding='utf-8')
    return report_path, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Report record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.reproducibility-report'
            or record.get('generatorSha256') != sha(Path(__file__))
            or set(record.get('sources', {})) != set(SOURCE_NAMES + ('config', 'policy'))):
        raise ValueError('Report generator or source contract changed.')
    paths = {name: entry['path'] for name, entry in record['sources'].items()}
    for name, entry in record['sources'].items():
        if sha(entry['path']) != entry['sha256']:
            raise ValueError(f'{name} source changed.')
    paths['report'] = str(path)
    sources = load_sources(paths, paths['config'], paths['policy'])
    markdown = render(paths, sources)
    if record['releaseVerdict'] != sources[0]['verdict']:
        raise ValueError('Release verdict changed.')
    md_path, html_path = path.with_suffix('.md'), path.with_suffix('.html')
    if (md_path.read_text(encoding='utf-8') != markdown or html_path.read_text(encoding='utf-8') != render_html(markdown)
            or sha(md_path) != record['markdownSha256'] or sha(html_path) != record['htmlSha256']):
        raise ValueError('Rendered report changed.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('generate', 'verify'))
    for name in SOURCE_NAMES:
        parser.add_argument('--' + name)
    parser.add_argument('--config')
    parser.add_argument('--policy', default=str(DEFAULT_POLICY))
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'generate':
        missing = [name for name in SOURCE_NAMES + ('config',) if not getattr(args, name)]
        if missing or not args.output_root:
            parser.error('generate requires all evidence sources, --config and --output-root: ' + ', '.join(missing))
        path, record = generate({name: getattr(args, name) for name in SOURCE_NAMES + ('config', 'policy')}, args.output_root)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, record = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'markdown': str(Path(path).with_suffix('.md')),
                      'html': str(Path(path).with_suffix('.html')), 'releaseVerdict': record['releaseVerdict']}))


if __name__ == '__main__':
    main()
