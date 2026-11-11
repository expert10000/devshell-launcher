"""Repeat accepted VTK reads and exercise bounded process controls."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psutil

from scientific_cgal_orientation_qualification import base, load, save, sha
from scientific_cgal_orientation_l7 import VTK, verify as verify_l7

SOURCE = Path(__file__).resolve()
MEMORY_LIMIT = 128 * 1024 * 1024
SLEEP_PROBE = "import pathlib,sys,time;print('started',flush=True);time.sleep(30);pathlib.Path(sys.argv[1]).write_text('unexpected')"
MEMORY_PROBE = "import pathlib,sys,time;blocks=[]\nwhile True:\n blocks.append(bytearray(16*1024*1024));time.sleep(.05)\npathlib.Path(sys.argv[1]).write_text('unexpected')"


def controlled_probe(python, code, marker, mode):
    started = time.monotonic()
    process = subprocess.Popen([str(python), '-c', code, str(marker)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    child = psutil.Process(process.pid)
    peak = 0
    try:
        while process.poll() is None:
            elapsed = time.monotonic() - started
            try:
                memory = child.memory_info().rss
            except psutil.NoSuchProcess:
                break
            peak = max(peak, memory)
            if ((mode == 'cancel' and elapsed >= .5)
                    or (mode == 'timeout' and elapsed >= 1)
                    or (mode == 'memory' and memory >= MEMORY_LIMIT)):
                process.kill()
                break
            if elapsed > 10:
                raise ValueError('Resilience probe did not reach its limit.')
            time.sleep(.01)
        process.communicate(timeout=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)
    if marker.exists() or process.returncode == 0:
        raise ValueError('Limited child published an artifact.')
    if mode == 'memory' and peak < MEMORY_LIMIT:
        raise ValueError('Memory probe never reached its budget.')
    return {'state': {'cancel': 'cancelled', 'timeout': 'timed-out', 'memory': 'limited'}[mode],
            'durationMs': round((time.monotonic()-started)*1000), 'peakRssBytes': peak,
            'limitBytes': MEMORY_LIMIT if mode == 'memory' else None,
            'outputAbsent': True}


def run(l7, vtk_python, output_root):
    support = verify_l7(l7)
    python = Path(vtk_python).resolve(strict=True)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    repeats = []
    for item in support['cases']:
        baseline = json.loads(Path(item['vtkPath']).read_text())
        for index in range(3):
            target = folder / f"{item['caseId']}-repeat-{index+1}.json"
            started = time.monotonic()
            process = subprocess.run([str(python), str(VTK), '--input', item['sourcePath'],
                                      '--result', str(target)], capture_output=True, text=True, timeout=60)
            if process.returncode:
                raise ValueError('Repeated VTK read failed: ' + (process.stderr or process.stdout)[-600:])
            observed = json.loads(target.read_text())
            if observed != baseline:
                raise ValueError('Repeated VTK orientation semantics changed.')
            repeats.append({'caseId': item['caseId'], 'repeat': index+1, 'path': str(target),
                            'sha256': sha(target), 'durationMs': round((time.monotonic()-started)*1000)})
    probes = {}
    for mode in ('cancel', 'timeout', 'memory'):
        probes[mode] = controlled_probe(python, MEMORY_PROBE if mode == 'memory' else SLEEP_PROBE,
                                       folder / f'{mode}-output.txt', mode)
    report = {**base('scientific.cgal-orientation-L8'), 'l8SourceSha256': sha(SOURCE),
              'l7Path': str(Path(l7).resolve()), 'l7Sha256': sha(l7),
              'vtkSourceSha256': sha(VTK), 'repeatCount': 3,
              'memoryLimitBytes': MEMORY_LIMIT, 'repeats': repeats, 'probes': probes}
    target = save(folder, 'l8.json', report)
    verify(target)
    return target


def verify(path):
    path, report = load(path, 'scientific.cgal-orientation-L8')
    if (report['l8SourceSha256'] != sha(SOURCE) or report['vtkSourceSha256'] != sha(VTK)
            or report['l7Sha256'] != sha(report['l7Path']) or report['repeatCount'] != 3
            or report['memoryLimitBytes'] != MEMORY_LIMIT):
        raise ValueError('Orientation L8 source identity changed.')
    support = verify_l7(report['l7Path'])
    expected = [(item, index) for item in support['cases'] for index in range(1, 4)]
    if len(report['repeats']) != len(expected):
        raise ValueError('Orientation L8 repeat count changed.')
    for saved, (item, index) in zip(report['repeats'], expected):
        target = Path(saved['path'])
        if (saved['caseId'] != item['caseId'] or saved['repeat'] != index
                or target.parent != path.parent or sha(target) != saved['sha256']
                or json.loads(target.read_text()) != json.loads(Path(item['vtkPath']).read_text())
                or saved['durationMs'] < 0):
            raise ValueError('Orientation L8 repeat changed.')
    for mode, expected_state in (('cancel', 'cancelled'), ('timeout', 'timed-out'), ('memory', 'limited')):
        probe = report['probes'][mode]
        if (probe['state'] != expected_state or probe['durationMs'] <= 0
                or probe['outputAbsent'] is not True
                or (path.parent / f'{mode}-output.txt').exists()):
            raise ValueError('Orientation L8 process limit changed.')
    if (report['probes']['memory']['peakRssBytes'] < MEMORY_LIMIT
            or report['probes']['memory']['limitBytes'] != MEMORY_LIMIT):
        raise ValueError('Orientation L8 memory cap was not observed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--vtk-python')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    target = run(args.source, args.vtk_python, args.output_root) if args.command == 'run' else Path(args.source).resolve()
    if args.command == 'verify':
        verify(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
