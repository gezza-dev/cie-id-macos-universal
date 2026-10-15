#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Export a clean source snapshot and all exact dependency archives for a built app."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
from publication_materials import ROOT, app_fingerprints, locked_archives, sha256, source_fingerprints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=['arm64', 'x86_64', 'universal2'], default=platform.machine())
    parser.add_argument('--variant', choices=['development', 'release'], default='development')
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'scripts/check-publication.py'), '--publish'], check=True)
    source = source_fingerprints()
    archives = locked_archives()
    variant = 'release' if args.variant == 'release' else ''
    build_receipt = ROOT / '.build/publication' / variant / (args.arch + '-build.json')
    if not build_receipt.is_file():
        raise RuntimeError('Build the app with build-native-app.py before preparing its source package')
    build = json.loads(build_receipt.read_text())
    app = ROOT / build['application']
    if source != build['source_files'] or app_fingerprints(app) != build['application_files']:
        raise RuntimeError('Application/source changed after the verified build; rebuild before packaging')
    output = ROOT / 'dist' / variant / args.arch
    output.mkdir(parents=True, exist_ok=True)
    package = output / 'cie-corresponding-source.tar.gz'
    index = {'schema_version': 1, 'source_files': source, 'archives': archives,
             'application': build['application'], 'application_files': build['application_files'],
             'build_environment': build['build_environment']}
    with tempfile.TemporaryDirectory(prefix='cie-source-', dir=output) as temporary:
        temporary = Path(temporary)
        metadata = temporary / 'SOURCE_MANIFEST.json'
        metadata.write_text(json.dumps(index, indent=2) + '\n')
        staged = temporary / package.name
        with tarfile.open(staged, 'w:gz') as bundle:
            bundle.add(metadata, arcname='SOURCE_MANIFEST.json')
            for name in source:
                bundle.add(ROOT / name, arcname='cie-middleware-macos/' + name, recursive=False)
            for item in archives:
                name = '.build/dependencies/downloads/' + item['archive']
                bundle.add(ROOT / name, arcname='cie-middleware-macos/' + name, recursive=False)
        # Read and hash every archived byte; a readable tar header alone is insufficient.
        with tarfile.open(staged, 'r:gz') as bundle:
            import hashlib
            for name, expected in source.items():
                member = bundle.extractfile('cie-middleware-macos/' + name)
                if member is None or hashlib.sha256(member.read()).hexdigest() != expected:
                    raise RuntimeError('Source archive integrity failed: ' + name)
            for item in archives:
                member = bundle.extractfile('cie-middleware-macos/.build/dependencies/downloads/' + item['archive'])
                if member is None or hashlib.sha256(member.read()).hexdigest() != item['sha256']:
                    raise RuntimeError('Dependency archive integrity failed: ' + item['archive'])
        staged.replace(package)
    index.update(package=str(package.relative_to(ROOT)), package_sha256=sha256(package))
    receipt = ROOT / '.build/publication' / variant / (args.arch + '-source-package.json')
    receipt.write_text(json.dumps(index, indent=2) + '\n')
    print(f'Prepared {len(source)} project files and {len(archives)} exact dependency source archives: {package}')
    subprocess.run([sys.executable, str(ROOT / 'scripts/check-publication.py'), '--release', '--arch', args.arch,
                    '--variant', args.variant], check=True)


if __name__ == '__main__':
    main()
