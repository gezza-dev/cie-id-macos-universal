#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Notarize, staple and package a verified Developer ID Universal Release.

Only a keychain profile name is accepted: passwords and private API keys never
enter command arguments, receipts, source packages or distribution archives.
A pending submission is resumed on the next invocation instead of uploaded twice.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from publication_materials import ROOT, app_fingerprints, sha256, source_fingerprints

spec = importlib.util.spec_from_file_location("universal_builder", ROOT / "scripts/build-universal-app.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
RECEIPTS = ROOT / ".build/publication/release"


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def notary(profile, *arguments):
    return json.loads(subprocess.check_output(
        ["xcrun", "notarytool", *map(str, arguments), "--keychain-profile", profile,
         "--output-format", "json", "--no-progress"], text=True))


def check_build(receipt, app):
    if (receipt["source_files"] != source_fingerprints() or
            receipt["application_files"] != app_fingerprints(app)):
        raise RuntimeError("Source or app changed after the verified Release build; rebuild before notarizing")
    environment = receipt["build_environment"]
    if (environment.get("signing_kind") != "developer-id" or
            environment["configuration"] != "Release" or environment["architecture"] != "universal2"):
        raise RuntimeError("Build a Developer ID Release Universal first")
    inventory = builder.inventory(app)
    binaries = [path for path, (kind, _) in inventory.items() if kind == "macho"]
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    expected = {Path("Contents/MacOS") / info["CFBundleExecutable"],
                builder.EXTENSION / "Contents/MacOS/CIEToken", *builder.MIDDLEWARES}
    if set(binaries) != expected:
        raise RuntimeError("Unexpected Release code layout; preview/debug code must not be shipped")
    for relative in binaries:
        builder.native.verify_binary(app / relative, builder.ARCHITECTURES)
    team = environment["identity_settings"]["DEVELOPMENT_TEAM"]
    builder.native.verify_signature(app, [app / path for path in binaries], team, builder.ARCHITECTURES, True)
    for relative in (Path("."), builder.EXTENSION):
        bundle = plistlib.loads((app / relative / "Contents/Info.plist").read_bytes())
        if (bundle["CFBundleShortVersionString"] != info["CFBundleShortVersionString"] or
                bundle.get("CFBundleVersion") != info["CFBundleVersion"]):
            raise RuntimeError("App and extension must have matching nonempty version/build numbers")
    return binaries, info["CFBundleShortVersionString"]


def zip_app(app, archive):
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cie-zip-", dir=archive.parent) as temporary:
        staged = Path(temporary) / archive.name
        builder.native.run("ditto", "-c", "-k", "--keepParent", app, staged)
        staged.replace(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="notarytool keychain profile name")
    parser.add_argument("--timeout", type=int, default=45, help="Seconds to wait per invocation (1–60); rerun to resume")
    parser.add_argument("--submit-only", action="store_true", help="Submit/resume without waiting or packaging")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    build_path = RECEIPTS / "universal2-build.json"
    build = json.loads(build_path.read_text())
    app = (ROOT / build["application"]).resolve()
    binaries, version = check_build(build, app)
    job_path = RECEIPTS / "universal2-notarization.json"
    job = json.loads(job_path.read_text()) if job_path.exists() else {}
    if (job.get("source_files") != build["source_files"] or
            job.get("application_files") != build["application_files"]):
        submission = ROOT / ".build/notarization/release" / ("CIE-ID-" + version + "-universal2-submission.zip")
        zip_app(app, submission)
        response = notary(args.profile, "submit", submission, "--no-wait")
        job = dict(id=response["id"], status=response.get("status", "In Progress"),
                   source_files=build["source_files"], application_files=build["application_files"],
                   upload_sha256=sha256(submission), profile=args.profile)
        save(job_path, job)
        save(RECEIPTS / ("notarization-" + job["id"] + ".json"), job)
        print("Submitted to Apple: " + job["id"], flush=True)
    else:
        print("Resuming Apple submission: " + job["id"], flush=True)
    if args.submit_only:
        return 0
    status = notary(args.profile, "info", job["id"])
    if status["status"] == "In Progress":
        # A timeout leaves the submission on Apple's servers. Query its current
        # status afterwards; any authentication/network error still propagates.
        subprocess.run(["xcrun", "notarytool", "wait", job["id"], "--keychain-profile", args.profile,
                        "--timeout", str(args.timeout) + "s", "--output-format", "json", "--no-progress"], check=False)
        status = notary(args.profile, "info", job["id"])
    job.update(status=status["status"], response=status)
    save(job_path, job)
    if status["status"] == "In Progress":
        print("Apple is still processing this submission. Rerun the same command to resume.", flush=True)
        return 75
    log = RECEIPTS / ("notarization-" + job["id"] + "-log.json")
    builder.native.run("xcrun", "notarytool", "log", job["id"], "--keychain-profile", args.profile, log)
    if status["status"] != "Accepted":
        raise RuntimeError("Apple rejected the submission; see " + str(log))
    # Recheck all inputs before stapling. Stapling changes bundle metadata, so
    # refresh the application receipt before binding corresponding sources.
    check_build(build, app)
    builder.native.run("xcrun", "stapler", "staple", app)
    builder.native.run("xcrun", "stapler", "validate", app)
    builder.native.verify_signature(app, [app / path for path in binaries],
        build["build_environment"]["identity_settings"]["DEVELOPMENT_TEAM"], builder.ARCHITECTURES, True)
    builder.native.run("spctl", "--assess", "--type", "execute", "--verbose=4", app)
    if shutil.which("syspolicy_check"):
        builder.native.run("syspolicy_check", "distribution", app)
    build["application_files"] = app_fingerprints(app)
    build["build_environment"]["notarization"] = dict(id=job["id"], status="Accepted", stapled=True)
    save(build_path, build)
    job["application_files"] = build["application_files"]
    save(job_path, job)
    builder.native.run(sys.executable, ROOT / "scripts/prepare-source-package.py", "--arch", "universal2", "--variant", "release")
    destination = app.parent
    final_zip = destination / ("CIE-ID-" + version + "-universal2.zip")
    zip_app(app, final_zip)
    # Validate the bundle recovered from the actual delivery ZIP, including its
    # offline ticket, rather than merely checking the working app directory.
    with tempfile.TemporaryDirectory(prefix="cie-delivery-check-") as directory:
        extracted = Path(directory) / app.name
        builder.native.run("ditto", "-x", "-k", final_zip, directory)
        builder.native.run("xcrun", "stapler", "validate", extracted)
        builder.native.verify_signature(extracted, [extracted / path for path in binaries],
            build["build_environment"]["identity_settings"]["DEVELOPMENT_TEAM"], builder.ARCHITECTURES, True)
        builder.native.run("spctl", "--assess", "--type", "execute", "--verbose=4", extracted)
    source_archive = ROOT / "dist/release/universal2/cie-corresponding-source.tar.gz"
    delivered_sources = destination / ("CIE-ID-" + version + "-corresponding-source.tar.gz")
    shutil.copyfile(source_archive, delivered_sources)
    hashes = {path.name: sha256(path) for path in (final_zip, delivered_sources)}
    (destination / "SHA256SUMS.txt").write_text("".join(value + "  " + name + "\n" for name, value in hashes.items()))
    delivery = dict(version=version, configuration="Release", architectures=list(builder.ARCHITECTURES),
                    notarization_id=job["id"], notarization_status="Accepted", stapled=True,
                    gatekeeper="accepted", application=str(app), artifacts=hashes)
    save(RECEIPTS / "universal2-distribution.json", delivery)
    save(destination / "RELEASE.json", delivery)
    print("Distribution ready: " + str(final_zip), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
