#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Preview, sign, notarize and verify a distribution DMG for a verified Release.

Requires ds_store 1.3.1. Run preview, inspect its Finder window, then prepare
with --preview-verified. Credentials are read only from a notarytool profile.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from publication_materials import app_fingerprints, sha256
from ds_store import DSStore
spec = importlib.util.spec_from_file_location('notarize_release', ROOT / 'scripts/notarize-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
R = release.RECEIPTS
build = json.loads((R / 'universal2-build.json').read_text())
app = (ROOT / build['application']).resolve()
version = plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']
# Stable asset names keep /releases/latest/download links valid across releases.
dmg = app.parent / 'CIE-ID-Universal.dmg'
jobfile = R / 'universal2-dmg-notarization.json'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', choices=['preview', 'prepare', 'submit', 'finalize'])
parser.add_argument('--profile', required=True)
parser.add_argument('--identity', required=True)
parser.add_argument('--preview-verified', action='store_true')
args = parser.parse_args()
profile = args.profile
identity = args.identity
preview = R / 'dmg-preview'
preview_image = preview / 'layout-preview.dmg'
preview_mount = preview / 'volume'
layout = dict(window_size=[640, 420], icons={'CIE ID.app':[175,155], 'Applicazioni':[465,155]})
run = release.builder.native.run

def validate_app(candidate):
    if app_fingerprints(candidate) != build['application_files']:
        raise RuntimeError('Packaged application differs from the verified Release')
    run('codesign', '--verify', '--deep', '--strict', '--verbose=2', candidate)
    run('xcrun', 'stapler', 'validate', candidate)
    run('spctl', '--assess', '--type', 'execute', '--verbose=4', candidate)
    for binary in release.builder.inventory(candidate):
        if release.builder.inventory(candidate)[binary][0] == 'macho':
            release.builder.native.verify_binary(candidate / binary, ['arm64', 'x86_64'])

def stage_contents(stage):
    stage.mkdir()
    run('ditto', app, stage / app.name)
    (stage / 'Applicazioni').symlink_to('/Applications')
    with DSStore.open(str(stage / '.DS_Store'), 'w+') as store:
        store['.']['vSrn'] = ('long', 1)
        store['.']['icvl'] = ('type', b'icnv')
        store['.']['vstl'] = ('type', b'icnv')
        store['.']['bwsp'] = dict(ShowStatusBar=False, WindowBounds='{{240, 180}, {640, 420}}',
            ContainerShowSidebar=False, PreviewPaneVisibility=False, SidebarWidth=0,
            ShowTabView=False, ShowToolbar=False, ShowPathbar=False, ShowSidebar=False)
        store['.']['icvp'] = dict(viewOptionsVersion=1, backgroundType=0,
            backgroundColorRed=1.0, backgroundColorGreen=1.0, backgroundColorBlue=1.0,
            gridOffsetX=0.0, gridOffsetY=0.0, gridSpacing=100.0, arrangeBy='none',
            showIconPreview=True, showItemInfo=False, labelOnBottom=True, textSize=14.0,
            iconSize=112.0, scrollPositionX=0.0, scrollPositionY=0.0)
        store[app.name]['Iloc'] = (175, 155)
        store['Applicazioni']['Iloc'] = (465, 155)

    validate_app(stage / app.name)

mode = args.mode
if mode == 'preview':
    release.check_build(build, app)
    if preview_image.exists():
        raise RuntimeError('Preview already exists; inspect it or remove only this temporary preview before retrying')
    preview.mkdir(parents=True, exist_ok=True)
    preview_mount.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cie-dmg-preview-', dir=app.parent) as temp:
        stage = Path(temp) / 'contents'
        stage_contents(stage)
        run('hdiutil', 'create', '-srcfolder', stage, '-volname', 'CIE ID ' + version,
            '-fs', 'HFS+', '-format', 'UDRW', preview_image)
    run('hdiutil', 'attach', '-nobrowse', '-noautoopen', '-mountpoint', preview_mount, preview_image)
    release.save(R / 'universal2-dmg-preview.json', dict(version=version, layout=layout,
        preview_mount=str(preview_mount), application_files=build['application_files']))
    print('Inspect this volume in Finder before prepare:', preview_mount, flush=True)
elif mode == 'prepare':
    release.check_build(build, app)
    proof = json.loads((R / 'universal2-dmg-preview.json').read_text())
    if not args.preview_verified or proof['layout'] != layout or proof['application_files'] != build['application_files']:
        raise RuntimeError('Inspect the matching preview in Finder, then pass --preview-verified')
    if preview_mount.is_mount():
        run('hdiutil', 'detach', preview_mount)
    assert not dmg.exists(), 'Refusing to overwrite an existing DMG'
    with tempfile.TemporaryDirectory(prefix='cie-dmg-', dir=app.parent) as temp:
        stage = Path(temp) / 'contents'
        stage_contents(stage)
        run('hdiutil', 'create', '-srcfolder', stage, '-volname', 'CIE ID ' + version,
            '-fs', 'HFS+', '-format', 'UDZO', '-imagekey', 'zlib-level=9', dmg)
    run('codesign', '--sign', identity, '--timestamp', '--identifier', 'it.giancarloezza.CIEID.dmg', dmg)
    run('codesign', '--verify', '--strict', '--verbose=2', dmg)
    release.save(R / 'universal2-dmg-build.json', dict(version=version, application=str(app),
        image=str(dmg), image_format='UDZO', volume_name='CIE ID ' + version,
        applications_link={'name':'Applicazioni','target':'/Applications'},
        layout={'CIE ID.app':[175,155],'Applicazioni':[465,155],'window_size':[640,420]},
        signing_identity=identity, application_files=build['application_files'],
        recipe_sha256=sha256(Path(__file__)), upload_sha256=sha256(dmg)))
    print('Signed DMG ready:', dmg, flush=True)
elif mode == 'submit':
    release.check_build(build, app)
    package = json.loads((R / 'universal2-dmg-build.json').read_text())
    assert sha256(dmg) == package['upload_sha256']
    if jobfile.exists():
        job = json.loads(jobfile.read_text())
        assert job['upload_sha256'] == package['upload_sha256']
        print('Resuming existing submission:', job['id'], flush=True)
    else:
        result = release.notary(profile, 'submit', dmg, '--no-wait')
        release.save(jobfile, dict(id=result['id'], status=result.get('status', 'In Progress'),
            upload_sha256=sha256(dmg), profile=profile, image=str(dmg)))
        print('Submitted to Apple:', result['id'], flush=True)
elif mode == 'finalize':
    release.check_build(build, app)
    job = json.loads(jobfile.read_text())
    result = release.notary(profile, 'info', job['id'])
    job.update(status=result['status'], response=result)
    release.save(jobfile, job)
    if result['status'] != 'Accepted':
        print(json.dumps(result), flush=True)
        sys.exit(75 if result['status'] == 'In Progress' else 1)
    run('xcrun', 'notarytool', 'log', job['id'], '--keychain-profile', profile,
        R / ('notarization-' + job['id'] + '-log.json'))
    assert sha256(dmg) == job.get('final_sha256', job['upload_sha256'])
    if not job.get('stapled'):
        run('xcrun', 'stapler', 'staple', dmg)
        job.update(stapled=True, final_sha256=sha256(dmg))
        release.save(jobfile, job)
    run('xcrun', 'stapler', 'validate', dmg)
    run('codesign', '--verify', '--strict', '--verbose=2', dmg)
    run('spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', '--verbose=4', dmg)
    run('hdiutil', 'verify', dmg)
    with tempfile.TemporaryDirectory(prefix='cie-dmg-check-') as temp:
        mount = Path(temp) / 'volume'
        mount.mkdir()
        attached = False
        try:
            subprocess.check_output(['hdiutil', 'attach', '-readonly', '-nobrowse', '-noautoopen',
                '-mountpoint', str(mount), '-plist', str(dmg)])
            attached = True
            assert (mount / 'Applicazioni').is_symlink()
            assert os.readlink(mount / 'Applicazioni') == '/Applications'
            assert {p.name for p in mount.iterdir() if not p.name.startswith('.')} == {'CIE ID.app','Applicazioni'}
            with DSStore.open(str(mount / '.DS_Store'), 'r') as store:
                assert store['.']['vstl'] == ('type', b'icnv')
                assert store['.']['bwsp']['WindowBounds'] == '{{240, 180}, {640, 420}}'
                assert store['CIE ID.app']['Iloc'] == (175, 155)
                assert store['Applicazioni']['Iloc'] == (465, 155)
            validate_app(mount / app.name)
            recovered = Path(temp) / app.name
            run('ditto', mount / app.name, recovered)
            validate_app(recovered)
            run('syspolicy_check', 'distribution', recovered)
        finally:
            if attached:
                run('hdiutil', 'detach', mount)
    release.check_build(build, app)
    delivery = json.loads((app.parent / 'RELEASE.json').read_text())
    for name, digest in delivery['artifacts'].items():
        if sha256(app.parent / name) != digest:
            raise RuntimeError('Existing artifact changed: ' + name)
    instructions = ROOT / 'Docs/releases' / version / 'INSTALLAZIONE.txt'
    delivered_instructions = app.parent / 'INSTALLAZIONE.txt'
    shutil.copyfile(instructions, delivered_instructions)
    delivered_sources = app.parent / 'CIE-ID-corresponding-source.tar.gz'
    delivery['artifacts'] = {path.name: sha256(path)
        for path in (dmg, delivered_sources, delivered_instructions)}
    delivery['disk_image'] = dict(file=dmg.name, notarization_id=job['id'],
        notarization_status='Accepted', stapled=True, gatekeeper='accepted', format='UDZO',
        applications_link='Applicazioni -> /Applications', verified_after_mount=True,
        verified_after_copy=True)
    release.save(app.parent / 'RELEASE.json', delivery)
    release.save(R / 'universal2-distribution.json', delivery)
    (app.parent / 'SHA256SUMS.txt').write_text(''.join(h + '  ' + name + '\n'
        for name, h in delivery['artifacts'].items()))
    job.update(verified=True, final_sha256=sha256(dmg))
    release.save(jobfile, job)
    print('Distribution DMG ready:', dmg, flush=True)
else:
    raise ValueError('Expected prepare, submit or finalize')
