"""Hold a broker worker until process-tree observation is attached."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gate', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--worker', required=True)
    parser.add_argument('--release')
    args = parser.parse_args()
    gate = Path(args.gate)
    deadline = time.monotonic() + 10
    while not gate.is_file():
        if time.monotonic() > deadline:
            raise TimeoutError('Broker process observation gate was not released.')
        time.sleep(0.005)
    if args.release:
        release = Path(args.release)
        deadline = time.monotonic() + 20
        while not release.is_file():
            if time.monotonic() > deadline:
                raise TimeoutError('Scientific concurrency release gate was not opened.')
            time.sleep(0.005)
    command = [args.python, args.adapter, '--request', args.request, '--worker', args.worker]
    child = subprocess.Popen(command, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    started = time.monotonic_ns()
    result = child.wait()
    timing = {'schemaVersion': 1, 'adapterPid': child.pid, 'startedMonotonicNs': started,
              'finishedMonotonicNs': time.monotonic_ns(), 'exitCode': result}
    (Path(args.request).parent / 'adapter-timing.json').write_text(json.dumps(timing, separators=(',', ':')),
                                                                encoding='utf-8')
    return result


if __name__ == '__main__':
    sys.exit(main())
