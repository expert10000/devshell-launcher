"""Versioned, conservative scientific suite dependency planner."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / 'schemas' / 'scientific-retest-graph.v1.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_graph(path=GRAPH):
    graph = json.loads(Path(path).read_text(encoding='utf-8'))
    if graph.get('schemaVersion') != 1 or not isinstance(graph.get('suites'), list):
        raise ValueError('Unsupported retest graph.')
    suites = {item['id']: item for item in graph['suites']}
    if len(suites) != len(graph['suites']):
        raise ValueError('Duplicate suite ID.')
    ordered, visiting, visited = [], set(), set()

    def visit(suite_id):
        if suite_id in visiting:
            raise ValueError('Cyclic suite dependency.')
        if suite_id in visited:
            return
        if suite_id not in suites:
            raise ValueError('Unknown suite dependency: ' + suite_id)
        visiting.add(suite_id)
        suite = suites[suite_id]
        if suite.get('runner') not in ('managed', 'managed-unqualified', 'local'):
            raise ValueError('Unknown suite runner.')
        if suite.get('managedAction') is not None:
            if suite['runner'] != 'managed' or not isinstance(suite['managedAction'], str) or not suite['managedAction']:
                raise ValueError('Invalid managed action.')
            if suite['managedAction'] == 'recipe' and suite.get('recipeId') not in ('compile-link', 'version'):
                raise ValueError('Invalid managed recipe.')
        for dependency in suite.get('dependsOn', []):
            visit(dependency)
        visiting.remove(suite_id)
        visited.add(suite_id)
        ordered.append(suite_id)

    for suite_id in suites:
        visit(suite_id)
    return graph, suites, ordered


def matches(path, pattern):
    path, pattern = path.replace('\\', '/'), pattern.replace('\\', '/')
    return fnmatch.fnmatchcase(path, pattern) or (pattern.endswith('/**') and path.startswith(pattern[:-3] + '/'))


def plan(changed_paths, changed_environment=(), graph_path=GRAPH):
    graph, suites, order = load_graph(graph_path)
    paths = sorted({path.replace('\\', '/').removeprefix('./') for path in changed_paths})
    environment = sorted(set(changed_environment))
    reasons = {suite_id: [] for suite_id in suites}
    unknown = []
    for path in paths:
        if any(matches(path, item) for item in graph.get('ignoredPaths', [])):
            continue
        matching = [sid for sid, suite in suites.items() if any(matches(path, pattern) for pattern in suite['inputs'])]
        if not matching:
            unknown.append(path)
        for sid in matching:
            reasons[sid].append('source:' + path)
    for key in environment:
        matching = [sid for sid, suite in suites.items() if key in suite['environment']]
        if not matching:
            unknown.append('environment:' + key)
        for sid in matching:
            reasons[sid].append('environment:' + key)
    if unknown:
        for sid in reasons:
            reasons[sid].append('conservative-unmapped-change')
    for sid in order:
        for child_id, child in suites.items():
            if sid in child['dependsOn'] and reasons[sid]:
                reasons[child_id].append('dependency:' + sid)
    return {'schemaVersion': 1, 'kind': 'scientific.retest-plan',
            'graphSha256': digest(graph_path), 'changedPaths': paths,
            'changedEnvironment': environment, 'unmappedChanges': unknown,
            'suites': [{'id': sid, 'provider': suites[sid]['provider'], 'runner': suites[sid]['runner'],
                        'reasons': sorted(set(reasons[sid])), 'command': suites[sid].get('command'),
                        'managedAction': suites[sid].get('managedAction'), 'recipeId': suites[sid].get('recipeId')}
                       for sid in order if reasons[sid]]}


def run_local(report, root=ROOT):
    for suite in report['suites']:
        if suite['runner'] != 'local':
            suite['execution'] = {'state': 'requires-managed-run'}
            continue
        if suite['id'] in ('broker.tests', 'pipeline.remote.tests', 'ci.release.regression.tests', 'environment.conformance.tests', 'advisor.cache.provenance.tests') and not os.environ.get('SCIENTIFIC_BROKER_CONFIG'):
            suite['execution'] = {'state': 'requires-broker-config'}
            continue
        command = suite['command']
        if (not isinstance(command, list) or command[:4] != ['python', '-m', 'unittest', 'discover']
                or any(not isinstance(part, str) for part in command)):
            raise ValueError('Local command is outside the fixed unittest allowlist.')
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
        suite['execution'] = {'state': 'passed' if completed.returncode == 0 else 'failed',
                              'exitCode': completed.returncode,
                              'output': (completed.stdout + completed.stderr)[-12000:]}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--changed', action='append', default=[])
    parser.add_argument('--environment-changed', action='append', default=[])
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--execute-local', action='store_true')
    parser.add_argument('--include-worktree', action='store_true',
                        help='Include modified and untracked source paths without changing Git state.')
    args = parser.parse_args()
    if not args.base and not args.changed and not args.environment_changed:
        parser.error('Specify --base, --changed, or --environment-changed.')
    paths = list(args.changed)
    if args.base:
        paths += subprocess.check_output(['git', 'diff', '--name-only', args.base, args.head, '--'], cwd=ROOT, text=True).splitlines()
    if args.include_worktree:
        paths += subprocess.check_output(['git', 'diff', '--name-only', '--'], cwd=ROOT, text=True).splitlines()
        paths += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    report = plan(paths, args.environment_changed)
    report['source'] = {'base': subprocess.check_output(['git', 'rev-parse', args.base], cwd=ROOT, text=True).strip()
                         if args.base else None,
                        'head': subprocess.check_output(['git', 'rev-parse', args.head], cwd=ROOT, text=True).strip()
                         if args.base else None}
    if args.execute_local:
        run_local(report)
    output = Path(args.output_root).resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    with (output / 'retest-plan.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    (output / 'retest-plan.json.sha256').write_text(digest(output / 'retest-plan.json'), encoding='utf-8')
    print(json.dumps({'record': str(output / 'retest-plan.json'), 'selected': [s['id'] for s in report['suites']],
                      'pendingManaged': [s['id'] for s in report['suites'] if s['runner'] != 'local']}, indent=2))


if __name__ == '__main__':
    main()
