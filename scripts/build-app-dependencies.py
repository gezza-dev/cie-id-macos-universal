#!/usr/bin/env python3
"""Build the pinned SSZipArchive sources for the native app, without CocoaPods."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default="arm64")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("dependency_builder", ROOT / "scripts/build-dependencies.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    item = json.loads((ROOT / "scripts/app-dependencies.lock.json").read_text())["ssziparchive"]
    work = ROOT / ".build/app-dependencies" / args.arch
    prefix = ROOT / ".build/dependencies" / args.arch / "prefix"
    work.mkdir(parents=True, exist_ok=True)
    sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
    compiler = subprocess.check_output(["xcrun", "--find", "clang"], text=True).strip()
    identity = dict(source=item, arch=args.arch, sdk=sdk, deployment_target="12.0",
                    compiler=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
                    sdk_version=subprocess.check_output(["xcrun", "--show-sdk-version"], text=True).strip(),
                    recipe=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    stamp = work / "ssziparchive.json"
    if stamp.exists() and (prefix / "lib/libSSZipArchive.a").exists() and json.loads(stamp.read_text()) == identity:
        print("Already built: SSZipArchive " + args.arch)
        return
    archive = ROOT / ".build/dependencies/downloads" / item["archive"]
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(item["url"], timeout=60) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError("SSZipArchive checksum mismatch")
    sources = work / "sources"
    shutil.rmtree(sources, ignore_errors=True)
    sources.mkdir()
    source = helper.unpack(archive, sources) / "SSZipArchive"
    objects = work / "objects"
    shutil.rmtree(objects, ignore_errors=True)
    objects.mkdir()
    flags = ["-arch", args.arch, "-isysroot", sdk, "-mmacosx-version-min=12.0", "-O2", "-fPIC",
             "-I" + str(source), "-I" + str(source / "minizip"), "-I" + str(prefix / "include")]
    flags += ["-D" + value for value in ["HAVE_INTTYPES_H", "HAVE_PKCRYPT", "HAVE_STDINT_H",
              "HAVE_WZAES", "HAVE_ZLIB", "ZLIB_COMPAT", "HAVE_ICONV", "HAVE_ARC4RANDOM_BUF"]]
    with (work / "build.log").open("w") as log:
        for file in [source / "SSZipArchive.m", *sorted((source / "minizip").glob("*.c"))]:
            objc_flags = ["-fobjc-arc"] if file.suffix == ".m" else []
            subprocess.run([compiler, *flags, *objc_flags, "-c", file, "-o", objects / (file.stem + ".o")],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["ar", "rcs", prefix / "lib/libSSZipArchive.a", *sorted(objects.glob("*.o"))], check=True)
    headers = prefix / "include/SSZipArchive"
    headers.mkdir(exist_ok=True)
    for file in source.glob("*.h"):
        shutil.copy2(file, headers)
    resources = prefix / "share/SSZipArchive"
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "Supporting Files/PrivacyInfo.xcprivacy", resources)
    shutil.copy2(source.parent / "LICENSE.txt", resources)
    shutil.copy2(source / "minizip/LICENSE", resources / "minizip-LICENSE")
    arches = subprocess.check_output(["lipo", "-archs", prefix / "lib/libSSZipArchive.a"], text=True).split()
    if arches != [args.arch]:
        raise ValueError("Unexpected SSZipArchive architecture")
    stamp.write_text(json.dumps(identity, indent=2) + "\n")
    print("Built native SSZipArchive " + args.arch)


if __name__ == "__main__":
    main()
