"""Allowlisted guarded remesh transport and release gate linked to repair/volume."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_qualification import (base, fixture_manifest, load, managed_case,
                                                   save, sha, verify_case, verify_l5, verify_l6)
from scientific_cgal_remesh_l7 import verify as verify_l7
from scientific_cgal_remesh_l8 import verify as verify_l8
from scientific_cgal_remesh_l9 import verify as verify_l9
from coexistence import verify as verify_coexistence

SOURCE = Path(__file__).resolve()
ALLOWED = ('accepted', 'volume-loss', 'affine-accepted', 'affine-volume-loss',
           'cube-accepted', 'cube-volume-loss', 'octa-accepted', 'octa-volume-loss')


def commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def chain(l9):
    final = verify_l9(l9)
    l8 = verify_l8(final['l8Path'])
    l7 = verify_l7(l8['l7Path'])
    l6 = verify_l6(l7['l6Path'])
    l5 = verify_l5(l6['reproductionPath'])
    return final, l5


class RemeshBroker:
    def __init__(self, l9, output_root):
        self.l9, self.l5 = chain(l9)
        self.root = Path(output_root).resolve()
        self.fixtures = {item['caseId']: item for item in fixture_manifest()['cases']}
        self.accepted = {item['caseId']: item['sourceSha256'] for item in self.l9['cases']}

    def submit(self, case_id):
        if case_id not in ALLOWED or case_id not in self.fixtures:
            raise ValueError('Remesh broker case is outside the certified fixture scope.')
        item = self.fixtures[case_id]
        worker, prefix = Path(self.l5['workerPath']), Path(self.l5['runtimePrefix'])
        folder = self.root / uuid.uuid4().hex
        folder.mkdir(parents=True)
        saved = managed_case(item, worker, prefix, folder)
        verify_case(saved, item)
        if item['expected'] == 'accepted' and saved['outputSha256'] != self.accepted[case_id]:
            raise ValueError('Broker remesh bytes differ from L9 certified output.')
        return saved

    def promote(self, saved):
        case_id = saved['caseId']
        if case_id not in self.accepted or saved['outputSha256'] != self.accepted[case_id]:
            raise ValueError('Only an L9 accepted guarded remesh can be promoted.')
        verify_case(saved, self.fixtures[case_id])
        return {'decision': 'allowed', 'caseId': case_id,
                'path': str(Path(saved['directory']) / 'remeshed.obj'),
                'sha256': saved['outputSha256']}


def smoke(l9, output_root):
    broker = RemeshBroker(l9, output_root)
    folder = broker.root / uuid.uuid4().hex
    folder.mkdir(parents=True)
    outcomes = []
    for case_id in ALLOWED:
        result = broker.submit(case_id)
        promotion = broker.promote(result) if result['state'] == 'succeeded' else None
        if (promotion is None) != (broker.fixtures[case_id]['expected'] == 'rejected'):
            raise ValueError('Broker remesh publication decision changed.')
        outcomes.append({'caseId': case_id, 'result': result, 'promotion': promotion})
    report = {**base('scientific.cgal-remesh-broker-smoke'),
              'brokerSourceSha256': sha(SOURCE), 'sourceCommit': commit(),
              'l9Path': str(Path(l9).resolve()), 'l9Sha256': sha(l9), 'cases': outcomes}
    target = save(folder, 'broker-smoke.json', report)
    verify_smoke(target)
    return target


def verify_smoke(path):
    _, report = load(path, 'scientific.cgal-remesh-broker-smoke')
    if (report['brokerSourceSha256'] != sha(SOURCE) or report['sourceCommit'] != commit()
            or report['l9Sha256'] != sha(report['l9Path'])):
        raise ValueError('Remesh broker smoke source changed.')
    final, _ = chain(report['l9Path'])
    accepted = {item['caseId']: item['sourceSha256'] for item in final['cases']}
    fixtures = {item['caseId']: item for item in fixture_manifest()['cases']}
    if [item['caseId'] for item in report['cases']] != list(ALLOWED):
        raise ValueError('Remesh broker smoke case scope changed.')
    for outcome in report['cases']:
        case_id, saved, promotion = outcome['caseId'], outcome['result'], outcome['promotion']
        verify_case(saved, fixtures[case_id])
        if case_id in accepted:
            if (promotion is None or promotion['decision'] != 'allowed'
                    or promotion['sha256'] != accepted[case_id]
                    or promotion['path'] != str(Path(saved['directory']) / 'remeshed.obj')):
                raise ValueError('Remesh broker accepted promotion changed.')
        elif promotion is not None or saved['outputSha256'] is not None:
            raise ValueError('Remesh broker promoted a rejected candidate.')
    return report


def certify(l9, smoke_path, coexistence_path, output_root):
    final, _ = chain(l9)
    transport = verify_smoke(smoke_path)
    combined = verify_coexistence(coexistence_path)
    if (transport['l9Sha256'] != sha(l9) or transport['sourceCommit'] != commit()
            or combined['sourceCommit'] != commit()
            or Path(combined['repo']).resolve() != ROOT.resolve()):
        raise ValueError('Repair, volume and remesh were not qualified from one source commit.')
    report = {**base('scientific.cgal-remesh-scoped-release'),
              'brokerSourceSha256': sha(SOURCE), 'sourceCommit': commit(),
              'capabilityId': 'mesh.remesh', 'runtimeId': 'cgal-win-conda',
              'l9Path': str(Path(l9).resolve()), 'l9Sha256': sha(l9),
              'brokerSmokePath': str(Path(smoke_path).resolve()), 'brokerSmokeSha256': sha(smoke_path),
              'coexistencePath': str(Path(coexistence_path).resolve()),
              'coexistenceSha256': sha(coexistence_path),
              'repairRecordId': combined['profiles']['repair']['recordId'],
              'volumeRecordId': combined['profiles']['volume']['recordId'],
              'allowlistedCases': [item['caseId'] for item in final['cases']],
              'acceptedOutputSha256': {item['caseId']: item['sourceSha256'] for item in final['cases']}}
    target = save(Path(output_root).resolve() / uuid.uuid4().hex, 'remesh-release.json', report)
    verify_release(target)
    return target


def verify_release(path):
    _, report = load(path, 'scientific.cgal-remesh-scoped-release')
    if (report['brokerSourceSha256'] != sha(SOURCE) or report['sourceCommit'] != commit()
            or report['runtimeId'] != 'cgal-win-conda' or report['capabilityId'] != 'mesh.remesh'
            or report['l9Sha256'] != sha(report['l9Path'])
            or report['brokerSmokeSha256'] != sha(report['brokerSmokePath'])
            or report['coexistenceSha256'] != sha(report['coexistencePath'])):
        raise ValueError('Remesh scoped release source changed.')
    final, _ = chain(report['l9Path'])
    transport = verify_smoke(report['brokerSmokePath'])
    combined = verify_coexistence(report['coexistencePath'])
    if (transport['l9Sha256'] != report['l9Sha256'] or combined['sourceCommit'] != commit()
            or Path(combined['repo']).resolve() != ROOT.resolve()
            or report['repairRecordId'] != combined['profiles']['repair']['recordId']
            or report['volumeRecordId'] != combined['profiles']['volume']['recordId']
            or report['allowlistedCases'] != [item['caseId'] for item in final['cases']]
            or report['acceptedOutputSha256'] != {item['caseId']: item['sourceSha256'] for item in final['cases']}):
        raise ValueError('Remesh release scope or lower qualification changed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('smoke', 'verify-smoke', 'certify', 'verify'))
    for name in ('l9', 'smoke-record', 'coexistence-record', 'output-root', 'record'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.command == 'smoke':
        target = smoke(args.l9, args.output_root)
    elif args.command == 'verify-smoke':
        target = Path(args.record).resolve()
        verify_smoke(target)
    elif args.command == 'certify':
        target = certify(args.l9, args.smoke_record, args.coexistence_record, args.output_root)
    else:
        target = Path(args.record).resolve()
        verify_release(target)
    print(json.dumps({'record': str(target), 'sha256': sha(target)}))
