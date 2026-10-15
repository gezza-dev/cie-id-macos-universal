#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Build, merge, test and sign a complete Universal app."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from publication_materials import ROOT, app_fingerprints, sha256, source_fingerprints

ARCHITECTURES = ("arm64", "x86_64")
EXTENSION = Path("Contents/PlugIns/CIEToken.appex")
MIDDLEWARES = (Path("Contents/Frameworks/libcie-pkcs11.dylib"),
               EXTENSION / "Contents/Frameworks/libcie-pkcs11.dylib")
MACHO_MAGIC = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
               b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}
spec = importlib.util.spec_from_file_location("native_builder", ROOT / "scripts/build-native-app.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def output(*command):
    return subprocess.check_output([str(arg) for arg in command], text=True, stderr=subprocess.PIPE)


def inventory(app):
    result = {}
    for path in sorted(app.rglob("*")):
        relative = path.relative_to(app)
        if "_CodeSignature" in relative.parts:
            continue
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            with path.open("rb") as stream:
                magic = stream.read(4)
            result[relative] = ("macho", None) if magic in MACHO_MAGIC else ("resource", sha256(path))
        elif path.is_dir():
            result[relative] = ("directory", None)
    return result


def signature_description(path, arch):
    return subprocess.check_output(["codesign", "-d", "--arch", arch, "--verbose=4", str(path)],
                                   stderr=subprocess.STDOUT, text=True)


def load_build(arch, snapshot, configuration, developer_id=False):
    receipt = ROOT / ".build/publication" / ("release" if developer_id else "") / (arch + "-build.json")
    build = json.loads(receipt.read_text())
    environment = build["build_environment"]
    app = ROOT / build["application"]
    if (build["source_files"] != snapshot or app_fingerprints(app) != build["application_files"] or
            environment["architecture"] != arch or environment["configuration"] != configuration or
            not environment["signed"] or environment.get("signing_kind", "development") !=
            ("developer-id" if developer_id else "development")):
        raise RuntimeError("Missing, stale, unsigned or incompatible build: " + arch)
    return app, build


def compiled_interface_matches(apps, differences, verified_sources):
    """AppKit nibs are CPU-neutral, but ibtool randomizes UUIDs/object ordering.

    Reuse the complete ARM storyboard only for receipts built from the exact
    same inputs and Xcode. Asset payloads must still match via assetutil's
    rendition digests; only the catalog compilation timestamp may differ.
    """
    if not verified_sources:
        return set()
    allowed = set()
    catalog = Path("Contents/Resources/Assets.car")
    if catalog in differences:
        catalogs = []
        for app in apps.values():
            records = json.loads(output("xcrun", "assetutil", "--info", app / catalog))
            records[0].pop("Timestamp", None)
            catalogs.append(records)
        if catalogs[0] == catalogs[1]:
            allowed.add(catalog)
    storyboard = Path("Contents/Resources/Base.lproj/Main.storyboardc")
    info_path = storyboard / "Info.plist"
    infos = []
    for app in apps.values():
        info = plistlib.loads((app / info_path).read_bytes())
        identifiers = info.pop("NSViewControllerIdentifiersToUUIDs")
        for value in identifiers.values():
            uuid.UUID(value)
        info["NSViewControllerIdentifiers"] = sorted(identifiers)
        infos.append(info)
    if infos[0] == infos[1]:
        for path in differences:
            if path == info_path:
                allowed.add(path)
            elif path.parent == storyboard and path.suffix == ".nib":
                headers = [(app / path).read_bytes()[:18] for app in apps.values()]
                if headers[0] == headers[1] and headers[0].startswith(b"NIBArchive"):
                    allowed.add(path)
    return allowed


def merge(apps, destination, verified_sources=False):
    inventories = {arch: inventory(apps[arch]) for arch in ARCHITECTURES}
    left, right = [inventories[arch] for arch in ARCHITECTURES]
    differences = {path for path in left.keys() | right.keys() if left.get(path) != right.get(path)}
    # Never excuse missing paths, changed resource types, symlinks or code.
    candidates = {path for path in differences if left.get(path, (None,))[0] == "resource"
                  and right.get(path, (None,))[0] == "resource"}
    accepted = compiled_interface_matches(apps, candidates, verified_sources) if candidates else set()
    differences -= accepted
    if differences:
        raise RuntimeError("Architecture builds contain different resources or bundle layouts: " + ", ".join(sorted(map(str, differences))[:15]))
    if accepted:
        print(f"Using shared AppKit resources from identical sources/Xcode ({len(accepted)} compiler metadata differences)", flush=True)
    binaries = [path for path, (kind, _) in left.items() if kind == "macho"]
    if len(binaries) < 4 or any(path not in binaries for path in MIDDLEWARES):
        raise RuntimeError("Missing application, CryptoTokenKit or embedded middleware executables")
    shutil.copytree(apps["arm64"], destination, symlinks=True)
    for directory in sorted(destination.rglob("_CodeSignature"), key=lambda p: len(p.parts), reverse=True):
        shutil.rmtree(directory)
    for relative in binaries:
        for arch in ARCHITECTURES:
            native.verify_binary(apps[arch] / relative, arch)
            build = output("vtool", "-arch", arch, "-show-build", apps[arch] / relative)
            if "platform MACOS" not in build or "minos 12.0" not in build:
                raise RuntimeError("Unexpected platform or deployment target: " + str(relative) + " " + arch)
        temporary = destination / (str(relative) + ".universal")
        native.run("lipo", "-create", *[apps[arch] / relative for arch in ARCHITECTURES], "-output", temporary)
        temporary.chmod((apps["arm64"] / relative).stat().st_mode & 0o777)
        temporary.replace(destination / relative)
        native.verify_binary(destination / relative, ARCHITECTURES)
    return binaries


def sign(apps, merged, binaries, team, temporary, developer_id=False):
    # Extract only the public certificate. Its SHA-1 selects the exact identity
    # used by Xcode without exporting a key or relying on an ambiguous name.
    prefix = temporary / "signing-cert-"
    native.run("codesign", "-d", "--extract-certificates=" + str(prefix), apps["arm64"])
    identity = hashlib.sha1(Path(str(prefix) + "0").read_bytes()).hexdigest().upper()
    main_executables = set()
    for relative in (Path("."), EXTENSION):
        info = plistlib.loads((merged / relative / "Contents/Info.plist").read_bytes())
        main_executables.add(relative / "Contents/MacOS" / info["CFBundleExecutable"])
    targets = [path for path in binaries if path not in main_executables] + [EXTENSION, Path(".")]
    for index, relative in enumerate(targets):
        expected = None
        for arch in ARCHITECTURES:
            original = apps[arch] / relative
            description = signature_description(original, arch)
            authority_name = "Developer ID Application:" if developer_id else "Apple Development:"
            if f"TeamIdentifier={team}" not in description or "Authority=" + authority_name not in description:
                raise RuntimeError("Unexpected signing identity: " + str(original))
            raw = subprocess.check_output(["codesign", "-d", "--arch", arch, "--entitlements", ":-", str(original)],
                                          stderr=subprocess.DEVNULL)
            entitlements = plistlib.loads(raw) if raw.strip() else {}
            identifier = next(line for line in description.splitlines() if line.startswith("Identifier="))
            authority = next(line for line in description.splitlines() if line.startswith("Authority="))
            metadata = (identifier, authority, entitlements)
            if expected is not None and metadata != expected:
                raise RuntimeError("Signing identity or entitlements differ between architectures: " + str(relative))
            expected = metadata
        entitlement_args = []
        if expected[2]:
            entitlement_file = temporary / ("entitlements-" + str(index) + ".plist")
            entitlement_file.write_bytes(plistlib.dumps(expected[2]))
            entitlement_args = ["--entitlements", entitlement_file, "--generate-entitlement-der"]
        # Sign from the leaves to the extension and finally the enclosing app.
        # Preserve identifiers, requirements and flags; never use --deep to sign.
        options = (["--timestamp", "--options", "runtime", "--preserve-metadata=identifier,requirements"] if developer_id else
                   ["--timestamp=none", "--preserve-metadata=identifier,requirements,flags,runtime"])
        native.run("codesign", "--force", "--sign", identity, *options, *entitlement_args, merged / relative)
    native.verify_signature(merged, [merged / path for path in binaries], team, ARCHITECTURES, developer_id)


def test_embedded_middleware(app):
    for arch in ARCHITECTURES:
        build = ROOT / ".build/native" / arch
        fixtures = build / "cie_sign_sdk/verification-fixtures"
        for relative in MIDDLEWARES:
            print("Testing merged middleware: " + arch + " " + str(relative), flush=True)
            native.run("arch", "-" + arch, build / "cie_middleware_tests", app / relative)
            native.run("arch", "-" + arch, build / "cie_verification_tests", fixtures, app / relative)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 6))
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Debug")
    parser.add_argument("--prepared-dependencies", action="store_true")
    parser.add_argument("--merge-only", action="store_true", help="Reuse matching verified signed architecture builds")
    parser.add_argument("--team", help="Override the Development Team for both builds")
    parser.add_argument("--sign-developer-id", action="store_true", help="Create a hardened Developer ID Release in dist/release")
    parser.add_argument("--signing-identity", help="Developer ID Application certificate name or SHA-1")
    parser.add_argument("--bundle-id", help="Override the bundle ID (required for Developer ID)")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("A positive job count is required")
    if args.sign_developer_id and (args.configuration != "Release" or not args.bundle_id):
        parser.error("Developer ID distribution requires --configuration Release and --bundle-id")
    if args.signing_identity and not args.sign_developer_id:
        parser.error("--signing-identity requires --sign-developer-id")
    variant = "release" if args.sign_developer_id else None
    # On Apple Silicon this also checks Rosetta before starting a long build.
    # Both architecture test executables must run; no emulated test is reported as native Intel hardware testing.
    for arch in ARCHITECTURES:
        native.run("arch", "-" + arch, "/usr/bin/true")
    native.run(sys.executable, ROOT / "tests/universal_bundle_tests.py")
    snapshot = source_fingerprints()
    settings_path = ROOT / "LocalSigning.xcconfig"
    settings = settings_path.read_bytes() if settings_path.exists() else None
    apps, builds = {}, {}
    for arch in ARCHITECTURES:
        if not args.merge_only:
            command = [sys.executable, ROOT / "scripts/build-native-app.py", "--arch", arch,
                       "--jobs", str(args.jobs), "--configuration", args.configuration,
                       "--sign-developer-id" if args.sign_developer_id else "--sign-development"]
            if args.prepared_dependencies:
                command.append("--prepared-dependencies")
            if args.team:
                command.extend(["--team", args.team])
            if args.bundle_id:
                command.extend(["--bundle-id", args.bundle_id])
            if args.signing_identity:
                command.extend(["--signing-identity", args.signing_identity])
            native.run(*command)
        apps[arch], builds[arch] = load_build(arch, snapshot, args.configuration, args.sign_developer_id)
    environments = [builds[arch]["build_environment"] for arch in ARCHITECTURES]
    for key in ("identity_settings", "deployment_target", "xcode", "macos", "configuration"):
        if environments[0][key] != environments[1][key]:
            raise RuntimeError("Architecture builds use different " + key)
    team = environments[0]["identity_settings"]["DEVELOPMENT_TEAM"]
    if args.team and team != args.team:
        raise RuntimeError("Requested team differs from architecture builds")
    if args.bundle_id and environments[0]["identity_settings"]["CIE_BUNDLE_ID"] != args.bundle_id:
        raise RuntimeError("Requested bundle ID differs from architecture builds")
    with tempfile.TemporaryDirectory(prefix="cie-universal2-") as directory:
        temporary = Path(directory)
        app = temporary / "CIE ID.app"
        binaries = merge(apps, app, verified_sources=True)
        sign(apps, app, binaries, team, temporary, args.sign_developer_id)
        test_embedded_middleware(app)
        if source_fingerprints() != snapshot or (settings_path.read_bytes() if settings_path.exists() else None) != settings:
            raise RuntimeError("Source or local signing settings changed during the Universal build")
        exported = native.export_app(app, "universal2", variant)
        native.verify_signature(exported, [exported / path for path in binaries], team, ARCHITECTURES, args.sign_developer_id)
        for relative in binaries:
            native.verify_binary(exported / relative, ARCHITECTURES)
    # The signing SDK is static inside each middleware slice. Also stage its
    # Universal archive for consumers rebuilding the middleware separately.
    sdk = ROOT / ".build/native" / (variant or "") / "universal2/libcie_sign_sdk.a"
    sdk.parent.mkdir(parents=True, exist_ok=True)
    native.run("lipo", "-create", *[ROOT / ".build/native" / arch / "cie_sign_sdk/libcie_sign_sdk.a"
                                    for arch in ARCHITECTURES], "-output", sdk)
    if set(output("lipo", "-archs", sdk).split()) != set(ARCHITECTURES):
        raise RuntimeError("Signing SDK is not Universal")
    environment = dict(environments[0], architecture="universal2", architectures=list(ARCHITECTURES),
                       command=["python3", "scripts/build-universal-app.py", *sys.argv[1:]],
                       architecture_builds={arch: builds[arch]["build_environment"] for arch in ARCHITECTURES},
                       signing_sdk=dict(path=str(sdk.relative_to(ROOT)), sha256=sha256(sdk)))
    receipt = ROOT / ".build/publication" / (variant or "") / "universal2-build.json"
    receipt.write_text(json.dumps(dict(source_files=snapshot, application=str(exported.relative_to(ROOT)),
                                      application_files=app_fingerprints(exported), build_environment=environment), indent=2) + "\n")
    kind = "Developer ID Application" if args.sign_developer_id else "Apple Development"
    print(f"Verified Universal app: {len(binaries)} Mach-O files, both architectures, {kind} signature", flush=True)
    print("Exported app: " + str(exported.resolve()), flush=True)


if __name__ == "__main__":
    main()
