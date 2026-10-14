"""Shared, local JSON execution boundary for scientific workers (schema 1)."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def statistics(values):
    result = dict(values or {})
    if 'vertices' in result:
        result['points'] = result['vertices']
    if 'faces' in result:
        result['triangles'] = result['faces']
    return result


class ScientificContract:
    def __init__(self, request_path, runtime_id, recipes):
        self.started = time.monotonic()
        self.completed = False
        self.request_path = Path(request_path).resolve(strict=True)
        if self.request_path.stat().st_size > 65536:
            raise ValueError('Request exceeds 64 KiB')
        self.request = json.loads(self.request_path.read_text(encoding='utf-8-sig'))
        self.directory = Path(self.request['workingDirectory']).resolve(strict=True)
        if self.directory != self.request_path.parent:
            raise ValueError('Working directory must contain the request')
        self.versions = {}
        previous_hook = sys.excepthook

        def failure_hook(kind, error, traceback):
            if not self.completed:
                try:
                    self.finish(state='failed', exit_code=1, diagnostics=[{'severity': 'error', 'message': str(error)[:4000]}])
                except Exception as result_error:
                    print(f'Could not write failure result: {result_error}', file=sys.stderr)
            previous_hook(kind, error, traceback)
        sys.excepthook = failure_hook
        if self.request.get('schemaVersion') != 1 or self.request.get('runtimeId') != runtime_id:
            raise ValueError('Unsupported runtime request')
        self.recipe = self.request.get('recipeId')
        if self.recipe not in recipes:
            raise ValueError('Unsupported mesh recipe')
        run_id = self.request.get('runId')
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
            raise ValueError('A bounded runId is required')
        self.dataset_root = Path(self.request['datasetRoot']).resolve(strict=True)
        self.input = Path(self.request['inputArtifacts'][0]['path']).resolve(strict=True)
        if not self.input.is_relative_to(self.dataset_root) or self.input.stat().st_size > 33554432:
            raise ValueError('Input must be a bounded local dataset copy')
        self.input_record = dict(self.request['inputArtifacts'][0])
        actual_hash = fingerprint(self.input)
        if self.input_record.get('sha256') and self.input_record['sha256'].lower() != actual_hash:
            raise ValueError('Dataset hash changed since the request was created')
        self.input_record.update(path=str(self.input), bytes=self.input.stat().st_size, sha256=actual_hash)
        self.output_name = self.request['outputArtifacts'][0]['path']
        extension = r'obj' if runtime_id == 'cgal-win-conda' else r'vtp'
        if not isinstance(self.output_name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.' + extension, self.output_name):
            raise ValueError('Output must be a safe mesh basename')
        self.output = self.directory / self.output_name
        if self.output.exists():
            raise ValueError('Output already exists')

    def finish(self, *, state='succeeded', exit_code=0, before=None, after=None,
               capabilities=None, diagnostics=None, scope='', extra=None):
        artifacts = []
        if state == 'succeeded' and self.output.is_file():
            artifacts.append({'path': self.output_name,
                              'mediaType': 'model/obj' if self.output.suffix == '.obj' else 'application/vnd.vtk.vtp',
                              'bytes': self.output.stat().st_size, 'sha256': fingerprint(self.output)})
        result = dict(extra or {})
        result.update(schemaVersion=1, runId=self.request.get('runId'), runtimeId=self.request.get('runtimeId'),
                      recipeId=self.recipe if hasattr(self, 'recipe') else self.request.get('recipeId'),
                      operation=self.request.get('operation', self.request.get('recipeId')),
                      state=state, exitCode=exit_code, durationMs=round((time.monotonic() - self.started) * 1000),
                      versions=self.versions, validatedCapabilities=capabilities or [],
                      before=statistics(before), after=statistics(after), diagnostics=diagnostics or [],
                      logReference='full.log', artifacts=artifacts,
                      inputArtifacts=[self.input_record] if hasattr(self, 'input_record') else [],
                      provenance=self.request.get('provenance', {}), scope=scope)
        temporary = self.directory / 'results.json.tmp'
        temporary.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, self.directory / 'results.json')
        self.completed = True
        print(json.dumps(result, allow_nan=False), flush=True)
        return result
