"""Inspect the explicit MATH3D tetrahedral consumer contract without granting L9."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(msh, checkout):
    msh = Path(msh).resolve(strict=True)
    checkout = Path(checkout).resolve(strict=True)
    if msh.suffix.lower() != '.msh' or not 100 <= msh.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError('A bounded tetrahedral MSH artifact is required.')
    path = checkout / 'scientific/volume-consumer.v1.json'
    contract = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    declares = isinstance(contract, dict) and all((
        contract.get('schemaVersion') == 1,
        contract.get('artifactType') == 'mesh.tetrahedral',
        contract.get('documentFormat') == 'math3d.volume-document',
        contract.get('preservesCells') is True,
    ))
    return {
        'schemaVersion': 1, 'capabilityId': 'mesh.generate3d',
        'sourceMshSha256': sha(msh),
        'requiredConsumerContract': 'scientific/volume-consumer.v1.json',
        'consumerContractSha256': sha(path) if path.is_file() else None,
        'declaresTetrahedralDocument': declares,
        'status': 'blocked',
        'reason': ('A declared volume consumer exists, but native tetrahedral document import, '
                   'independent reload and viewer regression have not been qualified.' if declares else
                   'MATH3D has no declared tetrahedral document consumer; its current OBJ importer '
                   'preserves the boundary surface only.'),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--msh', required=True)
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    result = assess(args.msh, args.checkout)
    Path(args.result).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
