"""Pin a single saved Boolean result as a local candidate broker case."""
import argparse
import json
from pathlib import Path

from typed_journey_broker import CAPABILITY, TypedJourneyBroker, sha, read


def create(args):
    result_path = Path(args.boolean_result).resolve(strict=True)
    result = read(result_path)
    config = {'schemaVersion': 1, 'profileKind': 'typed-journey', 'runtimeId': 'cgal-win-conda',
              'capabilityId': CAPABILITY, 'sourceRoot': str(Path(args.source_root).resolve(strict=True)),
              'math3dRoot': str(Path(args.math3d).resolve(strict=True)),
              'datasetRoot': str(Path(args.runs_root).resolve(strict=True)),
              'jobsRoot': str(Path(args.jobs_root).resolve()),
              'gmshPython': str(Path(args.gmsh_python).resolve(strict=True)),
              'vtkPython': str(Path(args.vtk_python).resolve(strict=True)),
              'node': str(Path(args.node).resolve(strict=True)),
              'caseProfile': {'caseId': args.case_id, 'sourceRunId': result['runId'],
                              'resultPath': str(result_path), 'resultSha256': sha(result_path),
                              'validationASha256': sha(result_path.parent / 'validation-a/results.json'),
                              'validationBSha256': sha(result_path.parent / 'validation-b/results.json')}}
    TypedJourneyBroker(config).verify()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'profile': str(output), 'sourceRunId': result['runId'],
                      'resultSha256': config['caseProfile']['resultSha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--math3d', required=True)
    parser.add_argument('--runs-root', required=True)
    parser.add_argument('--boolean-result', required=True)
    parser.add_argument('--jobs-root', required=True)
    parser.add_argument('--gmsh-python', required=True)
    parser.add_argument('--vtk-python', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--case-id', default='distinct-cubes')
    parser.add_argument('--output', required=True)
    create(parser.parse_args())
