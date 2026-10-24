"""Resolve byte-identical archived payloads without duplicating their storage.

Acquisition manifests retain their original logical paths and digests. Only
duplicate compressed output files are aliases; metadata and timing stay per run.
"""
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def aliases():
    return json.loads((ROOT / 'payload_aliases.json').read_text())['aliases']


def _relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def payload_exists(path):
    return Path(path).is_file() or _relative(path) in aliases()


def payload_bytes(path):
    path = Path(path)
    if path.is_file():
        return path.read_bytes()
    entry = aliases()[_relative(path)]
    target = (ROOT / entry['stored_path']).resolve()
    target.relative_to(ROOT)
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Payload hash mismatch: ' + str(path))
    return data


def raw_payload(path):
    path = Path(path)
    if payload_exists(path):
        return payload_bytes(path)
    return gzip.decompress(payload_bytes(Path(str(path) + '.gz')))


def verify_aliases():
    for logical, entry in aliases().items():
        assert logical.startswith('results/') and logical.endswith('.bin.gz'), logical
        assert not (ROOT / logical).exists(), logical
        assert entry['stored_path'] not in aliases(), 'Alias chains are not allowed'
        data = payload_bytes(ROOT / logical)
        assert len(data) == entry['size_bytes'], logical
    return len(aliases())
