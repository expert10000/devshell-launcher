"""Versioned scientific contract compatibility and fixture-backed migration checks."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from broker import sha

ROOT = Path(__file__).resolve().parents[2]
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')


def version(text):
    match = VERSION.fullmatch(text or '')
    if not match:
        raise ValueError('Contract version must be major.minor.patch.')
    return tuple(int(part) for part in match.groups())


def issue(path, kind, impact):
    return {'path': path, 'kind': kind, 'impact': impact}


def schema_changes(path, old, new):
    changes = []
    for key in ('type', 'pattern', 'format', 'additionalProperties'):
        if old.get(key) != new.get(key):
            changes.append(issue(path + '.' + key, key + '-changed', 'breaking'))
    old_enum, new_enum = old.get('enum'), new.get('enum')
    if old_enum is not None or new_enum is not None:
        if old_enum is None or new_enum is None:
            changes.append(issue(path + '.enum', 'enum-changed', 'breaking'))
        elif not set(map(json.dumps, old_enum)).issubset(set(map(json.dumps, new_enum))):
            changes.append(issue(path + '.enum', 'enum-narrowed', 'breaking'))
        elif old_enum != new_enum:
            changes.append(issue(path + '.enum', 'enum-expanded', 'additive'))
    previous, current = set(old.get('required', [])), set(new.get('required', []))
    for name in sorted(current - previous):
        changes.append(issue(path + '.required.' + name, 'required-added', 'breaking'))
    for name in sorted(previous - current):
        changes.append(issue(path + '.required.' + name, 'required-removed', 'additive'))
    before, after = old.get('properties', {}), new.get('properties', {})
    for name in sorted(before.keys() - after.keys()):
        changes.append(issue(path + '.properties.' + name, 'property-removed', 'breaking'))
    for name in sorted(after.keys() - before.keys()):
        changes.append(issue(path + '.properties.' + name, 'property-added',
                             'breaking' if name in current else 'additive'))
    for name in sorted(before.keys() & after.keys()):
        changes += schema_changes(path + '.properties.' + name, before[name], after[name])
    if old.get('items') or new.get('items'):
        if not old.get('items') or not new.get('items'):
            changes.append(issue(path + '.items', 'items-changed', 'breaking'))
        else:
            changes += schema_changes(path + '.items', old['items'], new['items'])
    return changes


def changes(old, new):
    if old.get('schemaId') != new.get('schemaId') or old.get('schemaVersion') != new.get('schemaVersion'):
        return [issue('registry', 'schema-identity-changed', 'breaking')]
    result = []
    for catalog in ('parameterSchemas', 'resultSchemas'):
        before, after = old.get(catalog, {}), new.get(catalog, {})
        for name in sorted(before.keys() - after.keys()):
            result.append(issue(catalog + '.' + name, 'schema-removed', 'breaking'))
        for name in sorted(after.keys() - before.keys()):
            result.append(issue(catalog + '.' + name, 'schema-added', 'additive'))
        for name in sorted(before.keys() & after.keys()):
            result += schema_changes(catalog + '.' + name, before[name], after[name])
    before = {item['id']: item for item in old.get('capabilities', [])}
    after = {item['id']: item for item in new.get('capabilities', [])}
    for name in sorted(before.keys() - after.keys()):
        result.append(issue('capabilities.' + name, 'capability-removed', 'breaking'))
    for name in sorted(after.keys() - before.keys()):
        result.append(issue('capabilities.' + name, 'capability-added', 'additive'))
    for name in sorted(before.keys() & after.keys()):
        left, right = before[name], after[name]
        for field in ('version', 'parametersSchema', 'resultSchema'):
            if left.get(field) != right.get(field):
                result.append(issue('capabilities.' + name + '.' + field, field + '-changed', 'breaking'))
        old_providers = {item['runtimeId'] for item in left.get('providers', [])}
        new_providers = {item['runtimeId'] for item in right.get('providers', [])}
        result += [issue('capabilities.' + name + '.providers.' + value, 'provider-removed', 'breaking')
                   for value in sorted(old_providers - new_providers)]
        result += [issue('capabilities.' + name + '.providers.' + value, 'provider-added', 'additive')
                   for value in sorted(new_providers - old_providers)]
    return result


def registry_valid(value):
    if (value.get('schemaVersion') != 1 or not isinstance(value.get('schemaId'), str)
            or not isinstance(value.get('parameterSchemas'), dict)
            or not isinstance(value.get('resultSchemas'), dict)
            or not isinstance(value.get('capabilities'), list)):
        return False
    ids = set()
    for item in value['capabilities']:
        if not isinstance(item, dict) or item.get('id') in ids or not isinstance(item.get('id'), str):
            return False
        ids.add(item['id'])
        if (type(item.get('version')) is not int or item['version'] < 1
                or item.get('parametersSchema') not in value['parameterSchemas']
                or item.get('resultSchema') not in value['resultSchemas']
                or not isinstance(item.get('providers'), list)):
            return False
        providers = [provider.get('runtimeId') for provider in item['providers'] if isinstance(provider, dict)]
        if len(providers) != len(item['providers']) or any(not isinstance(name, str) for name in providers) or len(set(providers)) != len(providers):
            return False
    return True


def validate(value, schema):
    kind = schema.get('type')
    correct = {'object': lambda: isinstance(value, dict), 'array': lambda: isinstance(value, list),
               'string': lambda: isinstance(value, str), 'integer': lambda: type(value) is int,
               'number': lambda: type(value) in (int, float), 'boolean': lambda: type(value) is bool}
    if kind in correct and not correct[kind]():
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if kind == 'string' and 'pattern' in schema and not re.fullmatch(schema['pattern'], value):
        return False
    if kind == 'object':
        props = schema.get('properties', {})
        if not set(schema.get('required', [])).issubset(value):
            return False
        if schema.get('additionalProperties') is False and not set(value).issubset(props):
            return False
        return all(validate(item, props[key]) for key, item in value.items() if key in props)
    if kind == 'array' and 'items' in schema:
        return all(validate(item, schema['items']) for item in value)
    return True


def migration_covers(rule, change, old, new):
    scope = rule.get('scope', '')
    operation = rule.get('operation')
    source, target = rule.get('from'), rule.get('to')
    if scope not in ('parameterSchemas.' + name for name in old.get('parameterSchemas', {})) and scope not in (
            'resultSchemas.' + name for name in old.get('resultSchemas', {})):
        return False
    catalog, name = scope.split('.', 1)
    before = old[catalog][name]
    after = new.get(catalog, {}).get(name)
    if not after or before.get('type') != 'object' or after.get('type') != 'object':
        return False
    if operation == 'rename-field':
        return (source in before.get('properties', {}) and target in after.get('properties', {})
                and change['path'] in (scope + '.properties.' + source, scope + '.required.' + target,
                                       scope + '.properties.' + target))
    if operation == 'set-default':
        return target in after.get('properties', {}) and change['path'] in (
            scope + '.required.' + target, scope + '.properties.' + target)
    return False


def fixture_passes(rule, old, new):
    try:
        catalog, name = rule['scope'].split('.', 1)
        before, after = old[catalog][name], new[catalog][name]
        example = rule['oldFixture']
        if not validate(example, before):
            return False
        transformed = dict(example)
        if rule['operation'] == 'rename-field':
            transformed[rule['to']] = transformed.pop(rule['from'])
        elif rule['operation'] == 'set-default':
            transformed.setdefault(rule['to'], rule['value'])
        else:
            return False
        return transformed == rule['newFixture'] and validate(transformed, after)
    except (KeyError, TypeError, ValueError):
        return False


def assess(old, new, old_version, new_version, rules):
    previous, current = version(old_version), version(new_version)
    if not registry_valid(old) or not registry_valid(new):
        return {'verdict': 'blocked', 'changes': [], 'uncovered': [], 'verifiedMigrationIds': [],
                'reasons': ['Baseline or current contract registry is malformed.']}
    found = changes(old, new)
    breaking = [item for item in found if item['impact'] == 'breaking']
    additive = [item for item in found if item['impact'] == 'additive']
    reasons = []
    if current < previous:
        reasons.append('Contract version moved backwards.')
    if additive and current[:2] == previous[:2]:
        reasons.append('Additive changes require a minor or major version bump.')
    if breaking and current[0] == previous[0]:
        reasons.append('Breaking changes require a major version bump.')
    verified_rules = [rule for rule in rules if fixture_passes(rule, old, new)]
    uncovered = [item for item in breaking if not any(migration_covers(rule, item, old, new) for rule in verified_rules)]
    if breaking and uncovered:
        reasons.append('Breaking changes lack a matching fixture-verified migration rule.')
    verdict = 'blocked' if reasons else 'migratable' if breaking else 'compatible'
    return {'verdict': verdict, 'changes': found, 'uncovered': uncovered,
            'verifiedMigrationIds': [item['id'] for item in verified_rules], 'reasons': reasons}


def within_repo(relative):
    path = (ROOT / relative).resolve(strict=True)
    if not path.is_relative_to(ROOT):
        raise ValueError('Contract path escapes the repository.')
    return path


def check(policy_path, output_root):
    policy_path = Path(policy_path).resolve(strict=True)
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != 1 or policy.get('kind') != 'scientific.contract-migration-policy':
        raise ValueError('Unsupported migration policy.')
    contracts = []
    for contract in policy['contracts']:
        before, after = within_repo(contract['baselinePath']), within_repo(contract['currentPath'])
        result = assess(json.loads(before.read_text(encoding='utf-8')),
                        json.loads(after.read_text(encoding='utf-8')),
                        contract['baselineVersion'], contract['currentVersion'], contract['migrations'])
        contracts.append({'id': contract['id'], 'baselinePath': contract['baselinePath'],
                          'currentPath': contract['currentPath'], 'baselineVersion': contract['baselineVersion'],
                          'currentVersion': contract['currentVersion'], 'baselineSha256': sha(before),
                          'currentSha256': sha(after), **result})
    report = {'schemaVersion': 1, 'kind': 'scientific.contract-compatibility',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'policySha256': sha(policy_path),
              'checkerSourceSha256': sha(Path(__file__)),
              'contracts': contracts, 'verdict': 'blocked' if any(item['verdict'] == 'blocked' for item in contracts) else 'passed'}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, report


def verify(path, policy_path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Compatibility report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if sha(policy_path) != report['policySha256'] or sha(Path(__file__)) != report.get('checkerSourceSha256'):
        raise ValueError('Migration policy changed.')
    policy = json.loads(Path(policy_path).read_text(encoding='utf-8'))
    if len(policy['contracts']) != len(report['contracts']):
        raise ValueError('Compatibility contract count changed.')
    for contract, recorded in zip(policy['contracts'], report['contracts']):
        before, after = within_repo(contract['baselinePath']), within_repo(contract['currentPath'])
        assessed = assess(json.loads(before.read_text()), json.loads(after.read_text()),
                          contract['baselineVersion'], contract['currentVersion'], contract['migrations'])
        if (recorded['id'] != contract['id'] or recorded['baselineSha256'] != sha(before)
                or recorded['currentSha256'] != sha(after)
                or any(recorded[key] != assessed[key] for key in assessed)):
            raise ValueError('Compatibility evidence no longer matches the contract files.')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'verify'])
    parser.add_argument('--policy', default=str(ROOT / 'schemas' / 'scientific-contract-migrations.v1.json'))
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'check':
        if not args.output_root:
            parser.error('check requires --output-root')
        path, report = check(args.policy, args.output_root)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, report = args.record, verify(args.record, args.policy)
    print(json.dumps({'record': str(path), 'verdict': report['verdict'], 'contracts': len(report['contracts'])}))
    if report['verdict'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
