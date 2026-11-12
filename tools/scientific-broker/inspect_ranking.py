"""Conservative paired ranking for current bounded inspection classes."""
import hashlib
import json
from pathlib import Path
import random
import statistics

from broker import sha
from class_inspect_qualification import verify as verify_classes
from inspect_classes import classify

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = 'schemas/scientific-inspect-ranking.v1.json'
PROVIDERS = {'cgal': 'cgal-win-conda', 'vtk': 'vtk-win-conda'}


def policy(repo=ROOT):
    path = Path(repo) / POLICY_PATH
    value = json.loads(path.read_text(encoding='utf-8'))
    expected = {'schemaVersion': 1, 'kind': 'scientific.mesh-inspect-ranking-policy',
                'operation': 'mesh.inspect', 'minimumPairedSamples': 5,
                'bootstrapIterations': 2000, 'confidence': .95,
                'minimumRelativeAdvantage': .1, 'maximumColdInvocationMs': 20000,
                'maximumWarmExecutionMs': 10000, 'maximumPeakRssMiB': 2048}
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError('Inspection ranking policy changed.')
    return value, sha(path)


def paired_interval(left, right, seed, iterations=2000):
    if len(left) != len(right) or len(left) < 5:
        raise ValueError('At least five paired inspection measurements are required.')
    differences = [a - b for a, b in zip(left, right)]
    rng = random.Random(seed)
    medians = sorted(statistics.median(rng.choices(differences, k=len(differences)))
                     for _ in range(iterations))
    return [medians[int(.025 * iterations)], medians[int(.975 * iterations) - 1]]


def rank_class(saved, class_id, ranking_policy):
    runs = saved['runs']
    count = len(runs['cgal'])
    if count < ranking_policy['minimumPairedSamples'] or len(runs['vtk']) != count:
        return {'recommendation': None, 'reason': 'Paired class evidence is incomplete.'}
    limits = {'coldInvocationMs': ranking_policy['maximumColdInvocationMs'],
              'warmExecutionMs': ranking_policy['maximumWarmExecutionMs']}
    for provider in PROVIDERS:
        for run in runs[provider]:
            if (not isinstance(run.get('peakRssBytes'), int)
                    or run['peakRssBytes'] > ranking_policy['maximumPeakRssMiB'] * 1024 * 1024
                    or any(not isinstance(run.get(key), (int, float)) or run[key] > limit or run[key] < 0
                           for key, limit in limits.items())):
                return {'recommendation': None, 'reason': 'Measured time or memory exceeds the ranking policy.'}
    phases = {}
    for phase in limits:
        cgal = [item[phase] for item in runs['cgal']]
        vtk = [item[phase] for item in runs['vtk']]
        medians = {PROVIDERS['cgal']: statistics.median(cgal),
                   PROVIDERS['vtk']: statistics.median(vtk)}
        seed = int.from_bytes(hashlib.sha256((class_id + ':' + phase).encode()).digest()[:8], 'big')
        interval = paired_interval(cgal, vtk, seed, ranking_policy['bootstrapIterations'])
        winner = PROVIDERS['cgal'] if interval[1] < 0 else PROVIDERS['vtk'] if interval[0] > 0 else None
        advantage = ((max(medians.values()) - min(medians.values())) / max(medians.values())
                     if max(medians.values()) > 0 else 0)
        phases[phase] = {'mediansMs': medians, 'pairedCgalMinusVtk95PctMs': interval,
                         'relativeAdvantage': advantage, 'winner': winner}
    cold, warm = phases['coldInvocationMs'], phases['warmExecutionMs']
    accepted = (cold['winner'] and cold['winner'] == warm['winner']
                and cold['relativeAdvantage'] >= ranking_policy['minimumRelativeAdvantage']
                and warm['relativeAdvantage'] >= ranking_policy['minimumRelativeAdvantage'])
    return {'recommendation': cold['winner'] if accepted else None,
            'reason': None if accepted else 'Paired cold and warm evidence is too close or disagrees.',
            'phases': phases,
            'peakRssMiB': {PROVIDERS[name]: round(saved['statistics'][name]['peakRssBytes'] / 1048576, 3)
                           for name in PROVIDERS}}


def decide(class_record, input_path, manual_provider=None):
    if manual_provider and manual_provider not in PROVIDERS.values():
        raise ValueError('Manual provider is outside the qualified inspection providers.')
    record = verify_classes(class_record)
    release_repo = json.loads(Path(record['releaseRecord']).read_text(encoding='utf-8'))['repo']
    ranking_policy, ranking_sha = policy(release_repo)
    try:
        scope = classify(input_path, release_repo)
    except (ValueError, OSError) as error:
        return {'state': 'abstained', 'recommendation': None, 'selectedProvider': None,
                'reason': 'Input has no qualified bounded class: ' + str(error)[:180],
                'classId': None, 'manualProvider': manual_provider,
                'inputSha256': sha(input_path), 'classRecordSha256': sha(class_record),
                'rankingPolicySha256': ranking_sha}
    class_id = scope['classId']
    if class_id not in record['classes']:
        raise ValueError('Input class lacks current desktop and broker evidence.')
    decision = rank_class(record['classes'][class_id], class_id, ranking_policy)
    recommendation = decision['recommendation']
    selected = manual_provider or recommendation
    return {'state': 'manual' if manual_provider else 'ranked' if recommendation else 'abstained',
            'recommendation': recommendation, 'selectedProvider': selected,
            'reason': 'Manual qualified provider retained.' if manual_provider else decision['reason'],
            'classId': class_id, 'manualProvider': manual_provider,
            'inputSha256': sha(input_path), 'classRecordSha256': sha(class_record),
            'rankingPolicySha256': ranking_sha, 'evidence': decision,
            'configPaths': record['configPaths']}
