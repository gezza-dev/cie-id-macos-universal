# SPDX-License-Identifier: BSD-3-Clause
"""Shared fingerprints for a source snapshot and its corresponding application."""
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprints(root=ROOT):
    if (root / '.git').exists():
        names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z',
                                         '--cached', '--others', '--exclude-standard']).decode().split('\0')
    else:
        # An exported source package deliberately has no upstream Git history.
        names = [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()
                 and not any(part in {'.git', '.build', 'dist', '__pycache__', 'xcuserdata'}
                             for part in p.relative_to(root).parts)]
    result = {}
    for name in sorted(set(names)):
        if not name:
            continue
        if Path(name).name == 'LocalSigning.xcconfig':
            continue
        if any(part in {'.git', '.build', 'dist', '__pycache__', 'xcuserdata', '.vscode', '.DS_Store'}
               for part in Path(name).parts):
            continue
        path = root / name
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError('Source export requires regular files inside the project: ' + name)
        if path.suffix.lower() in {'.p12', '.pfx', '.provisionprofile', '.mobileprovision',
                                  '.a', '.o', '.dylib', '.bin'}:
            raise RuntimeError('Unexpected private/generated file in source snapshot: ' + name)
        if re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----', path.read_bytes()):
            raise RuntimeError('Private key detected in source snapshot: ' + name)
        result[name] = sha256(path)
    return result


def app_fingerprints(app):
    return {str(path.relative_to(app)): sha256(path) for path in sorted(app.rglob('*'))
            if path.is_file() and not path.is_symlink()}


def locked_archives(root=ROOT):
    result = []
    for filename in ['dependencies.lock.json', 'app-dependencies.lock.json']:
        for component, item in json.loads((root / 'scripts' / filename).read_text()).items():
            path = root / '.build/dependencies/downloads' / item['archive']
            if not path.is_file() or sha256(path) != item['sha256']:
                raise RuntimeError('Missing or changed locked source archive: ' + item['archive'])
            result.append(dict(item, component=component))
    return result
