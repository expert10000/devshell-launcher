"""Verified content-addressed artifact store with references, pins and safe retention."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from broker import Broker
from smoke import verify_saved_smoke

HEX = re.compile(r'[0-9a-f]{64}\Z')


def digest_file(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


class Cache:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.objects = self.root / 'objects'
        self.temporary = self.root / 'tmp'
        self.objects.mkdir(parents=True, exist_ok=True)
        self.temporary.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / 'cache.sqlite3', timeout=30)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS objects (digest TEXT PRIMARY KEY, bytes INTEGER NOT NULL, created REAL NOT NULL, touched REAL NOT NULL)')
        if 'touched' not in {row[1] for row in self.db.execute('PRAGMA table_info(objects)')}:
            self.db.execute('ALTER TABLE objects ADD COLUMN touched REAL NOT NULL DEFAULT 0')
            self.db.execute('UPDATE objects SET touched=created')
        self.db.execute('CREATE TABLE IF NOT EXISTS refs (digest TEXT NOT NULL REFERENCES objects(digest) ON DELETE CASCADE, owner TEXT NOT NULL, PRIMARY KEY(digest,owner))')
        self.db.execute('CREATE TABLE IF NOT EXISTS pins (digest TEXT NOT NULL REFERENCES objects(digest) ON DELETE CASCADE, owner TEXT NOT NULL, PRIMARY KEY(digest,owner))')
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def path(self, digest):
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise ValueError('Expected a SHA-256 object identity.')
        target = self.objects / digest[:2] / digest
        if target.is_symlink() or target.parent.is_symlink() or not target.resolve().is_relative_to(self.objects.resolve()):
            raise ValueError('Cache object path escapes the store.')
        return target

    def put(self, source, owner):
        if not owner or len(owner) > 200:
            raise ValueError('A bounded source reference is required.')
        with tempfile.NamedTemporaryFile(dir=self.temporary, delete=False) as stream:
            temporary = Path(stream.name)
            digest = hashlib.sha256()
            size = 0
            try:
                with Path(source).open('rb') as incoming:
                    for block in iter(lambda: incoming.read(1024 * 1024), b''):
                        stream.write(block)
                        digest.update(block)
                        size += len(block)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        key = digest.hexdigest()
        target = self.path(key)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            target.parent.mkdir(exist_ok=True)
            if target.exists():
                if digest_file(target) != (key, size):
                    raise ValueError('Existing cache object hash or length changed.')
            else:
                os.replace(temporary, target)
            now = time.time()
            self.db.execute('INSERT OR IGNORE INTO objects (digest,bytes,created,touched) VALUES (?,?,?,?)', (key, size, now, now))
            self.db.execute('INSERT OR IGNORE INTO refs VALUES (?,?)', (key, owner))
            self.db.execute('UPDATE objects SET touched=? WHERE digest=?', (now, key))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return {'sha256': key, 'bytes': size, 'path': str(target), 'owner': owner}

    def get(self, digest):
        target = self.path(digest)
        row = self.db.execute('SELECT bytes FROM objects WHERE digest=?', (digest,)).fetchone()
        if row is None or not target.is_file() or digest_file(target) != (digest, row[0]):
            raise ValueError('Cache object is missing or changed.')
        return target

    def reference(self, digest, owner, pin=False, remove=False):
        self.get(digest)
        if not owner or len(owner) > 200:
            raise ValueError('A bounded owner is required.')
        table = 'pins' if pin else 'refs'
        with self.db:
            if remove:
                self.db.execute(f'DELETE FROM {table} WHERE digest=? AND owner=?', (digest, owner))
            else:
                self.db.execute(f'INSERT OR IGNORE INTO {table} VALUES (?,?)', (digest, owner))
            self.db.execute('UPDATE objects SET touched=? WHERE digest=?', (time.time(), digest))

    def inspect(self, digest):
        path = self.get(digest)
        refs = [row[0] for row in self.db.execute('SELECT owner FROM refs WHERE digest=? ORDER BY owner', (digest,))]
        pins = [row[0] for row in self.db.execute('SELECT owner FROM pins WHERE digest=? ORDER BY owner', (digest,))]
        return {'sha256': digest, 'bytes': path.stat().st_size, 'references': refs, 'pins': pins}

    def gc(self, older_than_days, dry_run=True):
        if older_than_days < 0:
            raise ValueError('Retention days cannot be negative.')
        cutoff = time.time() - older_than_days * 86400
        removed = []
        try:
            self.db.execute('BEGIN IMMEDIATE')
            rows = self.db.execute('SELECT digest FROM objects WHERE touched<=? AND '
                                   'NOT EXISTS(SELECT 1 FROM refs WHERE refs.digest=objects.digest) AND '
                                   'NOT EXISTS(SELECT 1 FROM pins WHERE pins.digest=objects.digest)', (cutoff,)).fetchall()
            for (digest,) in rows:
                path = self.get(digest)  # Corruption blocks cleanup; never silently discard evidence.
                removed.append(digest)
                if not dry_run:
                    path.unlink()
                    self.db.execute('DELETE FROM objects WHERE digest=?', (digest,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return {'dryRun': dry_run, 'eligible': removed}


def ingest_broker(cache, config, job_id, name):
    if not re.fullmatch('[0-9a-f]{32}', job_id):
        raise ValueError('Invalid broker job ID.')
    broker = Broker(config)
    raw = broker.artifact(job_id, name)
    with tempfile.NamedTemporaryFile(dir=cache.temporary, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        return cache.put(temporary, f'broker:{job_id}:{name}')
    finally:
        temporary.unlink(missing_ok=True)


def ingest_document(cache, config, job_id):
    if not re.fullmatch('[0-9a-f]{32}', job_id):
        raise ValueError('Invalid broker job ID.')
    broker = Broker(config)
    directory = broker.jobs_root / job_id
    verify_saved_smoke(directory)
    return cache.put(directory / 'product' / 'qualified-mesh.m3dm', f'math3d:{job_id}:qualified-mesh.m3dm')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['put', 'ingest-broker', 'ingest-document', 'get', 'reference', 'unreference', 'pin', 'unpin', 'gc'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--file')
    parser.add_argument('--config')
    parser.add_argument('--job-id')
    parser.add_argument('--name', default='l5-positive.obj')
    parser.add_argument('--digest')
    parser.add_argument('--owner')
    parser.add_argument('--older-than-days', type=float, default=30)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with Cache(args.root) as cache:
        if args.command == 'put':
            result = cache.put(args.file, args.owner)
        elif args.command == 'ingest-broker':
            result = ingest_broker(cache, args.config, args.job_id, args.name)
        elif args.command == 'ingest-document':
            result = ingest_document(cache, args.config, args.job_id)
        elif args.command == 'get':
            result = cache.inspect(args.digest)
        elif args.command == 'gc':
            result = cache.gc(args.older_than_days, dry_run=not args.apply)
        else:
            cache.reference(args.digest, args.owner, pin=args.command in ('pin', 'unpin'),
                            remove=args.command in ('unreference', 'unpin'))
            result = cache.inspect(args.digest)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
