#!/usr/bin/env python3
"""Build and verify the native middleware, CryptoTokenKit extension and macOS app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from publication_materials import app_fingerprints, source_fingerprints

ROOT = Path(__file__).resolve().parents[1]


def run(*command):
    subprocess.run([str(arg) for arg in command], check=True, cwd=ROOT)


def verify_binary(binary, arch):
    expected = [arch] if isinstance(arch, str) else list(arch)
    architectures = subprocess.check_output(["lipo", "-archs", binary], text=True).split()
    if sorted(architectures) != sorted(expected):
        raise RuntimeError(f"Unexpected architectures in {binary}: {architectures}")
    for architecture in expected:
        for line in subprocess.check_output(["otool", "-arch", architecture, "-L", binary], text=True).splitlines()[1:]:
            imported = line.strip().split(" (", 1)[0]
            if not imported.startswith(("/System/Library/", "/usr/lib/", "@rpath/", "@loader_path/")):
                raise RuntimeError(f"Non-system dynamic dependency in {binary} ({architecture}): {imported}")


def verify_signature(app, binaries, team, architectures=None, developer_id=False):
    run("codesign", "--verify", "--all-architectures", "--deep", "--strict", "--verbose=2", app)
    for binary in binaries:
        for architecture in architectures or [None]:
            selection = ["--arch", architecture] if architecture else []
            signature = subprocess.check_output(
                ["codesign", "-d", *selection, "--verbose=4", binary], stderr=subprocess.STDOUT, text=True)
            authority = "Developer ID Application:" if developer_id else "Apple Development:"
            if f"TeamIdentifier={team}" not in signature or "Authority=" + authority not in signature:
                raise RuntimeError(f"Unexpected signing identity: {binary} ({architecture})")
            if developer_id:
                if not re.search(r"flags=0x[0-9a-f]+\([^)]*\bruntime\b", signature) or "Timestamp=" not in signature:
                    raise RuntimeError(f"Missing hardened runtime or secure timestamp: {binary} ({architecture})")
                raw = subprocess.check_output(["codesign", "-d", *selection, "--entitlements", ":-", binary],
                                              stderr=subprocess.DEVNULL)
                entitlements = plistlib.loads(raw) if raw.strip() else {}
                if entitlements.get("com.apple.security.get-task-allow"):
                    raise RuntimeError(f"Debug entitlement in distribution code: {binary}")
    groups = []
    for bundle in [app, app / "Contents/PlugIns/CIEToken.appex"]:
        info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
        group = info["CIEAppGroupIdentifier"]
        for architecture in architectures or [None]:
            selection = ["--arch", architecture] if architecture else []
            entitlements = plistlib.loads(subprocess.check_output(
                ["codesign", "-d", *selection, "--entitlements", ":-", bundle], stderr=subprocess.DEVNULL))
            if (not group.startswith(team + ".") or
                    entitlements.get("com.apple.security.application-groups") != [group] or
                    not entitlements.get("com.apple.security.app-sandbox") or
                    not entitlements.get("com.apple.security.smartcard")):
                raise RuntimeError(f"Missing or inconsistent sandbox, smartcard or app group: {bundle} ({architecture})")
        groups.append(group)
    if groups[0] != groups[1]:
        raise RuntimeError("App and CryptoTokenKit extension use different application groups")


def export_app(app, arch, variant=None):
    # Publish outside the hidden build tree. File Provider can restore the
    # hidden flags of items under .build after chflags has cleared them.
    output = ROOT / "dist" / (variant or "") / arch
    output.mkdir(parents=True, exist_ok=True)
    synchronized = False
    for directory in [output, *output.parents]:
        attributes = subprocess.check_output(["xattr", str(directory)], text=True).splitlines()
        if any(name.startswith(("com.apple.fileprovider.", "com.apple.file-provider-domain-id"))
               or name == "com.apple.icloud.desktop" for name in attributes):
            synchronized = True
            break
    local_output = output
    if synchronized:
        # File Provider restores FinderInfo's bundle flag on .app directories,
        # invalidating strict codesign checks. Keep the real bundle outside it.
        local_output = Path.home() / "Developer/Builds/CIE-ID" / (variant or "") / arch
        local_output.mkdir(parents=True, exist_ok=True)
    destination = local_output / app.name
    with tempfile.TemporaryDirectory(prefix="cie-export-", dir=local_output) as temporary:
        temporary = Path(temporary)
        staged = temporary / app.name
        shutil.copytree(app, staged, symlinks=True)
        run("chflags", "-R", "nohidden", staged)
        previous = temporary / "previous.app"
        if destination.exists():
            destination.rename(previous)
        try:
            staged.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
        # Finder/File Provider can attach these metadata attributes while the
        # app is copied into Documents. They invalidate a strict signature check
        # even though no signed resource bytes changed.
        for path in [destination, *destination.rglob("*")]:
            if path.is_symlink():
                continue
            attributes = subprocess.check_output(["xattr", str(path)], text=True).splitlines()
            for attribute in ["com.apple.FinderInfo", "com.apple.ResourceFork"]:
                if attribute in attributes:
                    run("xattr", "-d", attribute, path)
    if synchronized:
        published = output / app.name
        with tempfile.TemporaryDirectory(prefix="cie-link-", dir=output) as temporary:
            temporary = Path(temporary)
            link = temporary / app.name
            link.symlink_to(destination, target_is_directory=True)
            previous = temporary / "previous.app"
            if published.exists() or published.is_symlink():
                published.rename(previous)
            try:
                link.rename(published)
            except OSError:
                if previous.exists() or previous.is_symlink():
                    previous.rename(published)
                raise
        print("Local signed-bundle location: " + str(destination), flush=True)
        return published
    return destination


def cloud_conflict_copy(name):
    # File Provider can create "header 2.h" copies in generated prefixes.
    # These are not dependency inputs and may be unavailable cloud placeholders.
    return re.search(r" [0-9]+(?:\.[^.]+)?$", name) is not None


def ignore_cloud_conflicts(directory, names):
    return [name for name in names if cloud_conflict_copy(name)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default=platform.machine())
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 6))
    parser.add_argument("--prepared-dependencies", action="store_true",
                        help="Reuse dependencies already built and verified by the dependency scripts")
    parser.add_argument("--prepare-only", action="store_true", help="Stage dependencies for Xcode")
    parser.add_argument("--clean", action="store_true", help="Clean Xcode products before building")
    parser.add_argument("--team", help="Development Team for a locally signed build")
    signing_mode = parser.add_mutually_exclusive_group()
    signing_mode.add_argument("--sign-development", action="store_true",
                        help="Sign with Apple Development using LocalSigning.xcconfig or --team")
    signing_mode.add_argument("--sign-developer-id", action="store_true",
                             help="Build a hardened Release with Developer ID Application")
    parser.add_argument("--signing-identity", help="Developer ID Application certificate name or SHA-1")
    parser.add_argument("--bundle-id", help="Override the app bundle ID (the app group follows it)")
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Release")
    args = parser.parse_args()
    if args.sign_developer_id and args.configuration != "Release":
        parser.error("Developer ID distribution requires --configuration Release")
    if args.signing_identity and not args.sign_developer_id:
        parser.error("--signing-identity requires --sign-developer-id")
    if args.sign_developer_id and not args.bundle_id:
        parser.error("Provide an explicit distribution --bundle-id")
    variant = "release" if args.sign_developer_id else None
    source_snapshot = source_fingerprints()
    local_signing = ROOT / "LocalSigning.xcconfig"
    local_settings = local_signing.read_bytes() if local_signing.exists() else None
    signed = bool(args.team or args.sign_development or args.sign_developer_id)
    if signed and not args.team and local_settings is None:
        parser.error("Provide --team or copy LocalSigning.xcconfig.example to LocalSigning.xcconfig")
    if not args.prepare_only:
        for compiler in ["ibtool", "actool"]:
            run("xcrun", "--find", compiler)
        run("xcodebuild", "-checkFirstLaunchStatus")
    run(sys.executable, ROOT / "scripts/check-publication.py")
    prefix = ROOT / ".build/dependencies" / args.arch / "prefix"
    if not args.prepared_dependencies:
        run(sys.executable, ROOT / "scripts/build-dependencies.py", "--arch", args.arch,
            "--jobs", args.jobs)
        run(sys.executable, ROOT / "scripts/build-app-dependencies.py", "--arch", args.arch)
    build = ROOT / ".build/native" / args.arch
    run("cmake", "-S", ROOT, "-B", build, "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_OSX_ARCHITECTURES=" + args.arch, "-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0",
        "-DCIE_DEPENDENCY_PREFIX=" + str(prefix))
    run("cmake", "--build", build, "--parallel", args.jobs)
    run("ctest", "--test-dir", build, "--output-on-failure")
    verify_binary(build / "libcie-pkcs11.dylib", args.arch)
    verify_binary(build / "CIEToken", args.arch)
    stage = ROOT / ".build/xcode-native" / args.arch
    stage.mkdir(parents=True, exist_ok=True)
    for folder in ["include", "lib", "share/SSZipArchive"]:
        shutil.copytree(prefix / folder, stage / folder, dirs_exist_ok=True, ignore=ignore_cloud_conflicts)
    shutil.copy2(build / "cie_sign_sdk/libcie_sign_sdk.a", stage / "lib")
    for archive in (stage / "lib").glob("*.a"):
        if cloud_conflict_copy(archive.name):
            continue
        architectures = subprocess.check_output(["lipo", "-archs", archive], text=True).split()
        if architectures != [args.arch]:
            raise RuntimeError(f"Unexpected architectures in {archive}: {architectures}")
    if args.prepare_only:
        print("Prepared native Xcode dependencies: " + str(stage))
        return
    # Xcode uses NSFileCoordinator to open project bundles. A File Provider
    # access claim in an iCloud checkout can wait indefinitely even when the
    # files are readable. Build an exact source copy on the local temp volume.
    workspace_holder = tempfile.TemporaryDirectory(prefix="cie-xcode-")
    xcode_root = Path(workspace_holder.name)
    for name in source_snapshot:
        destination = xcode_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    if local_settings is not None:
        (xcode_root / local_signing.name).write_bytes(local_settings)
    native_stage = xcode_root / ".build/xcode-native" / args.arch
    native_stage.parent.mkdir(parents=True)
    native_stage.symlink_to(stage, target_is_directory=True)
    derived = xcode_root / ".build/xcode" / args.arch
    print("Building Xcode from an isolated local source snapshot: " + str(xcode_root), flush=True)
    identity = args.signing_identity or ("Developer ID Application" if args.sign_developer_id else "Apple Development")
    signing = (["CODE_SIGN_IDENTITY=" + identity] +
               (["DEVELOPMENT_TEAM=" + args.team] if args.team else [])) if signed else ["CODE_SIGNING_ALLOWED=NO"]
    if args.bundle_id:
        signing.append("CIE_BUNDLE_ID=" + args.bundle_id)
    if args.sign_developer_id:
        signing.extend(["CODE_SIGN_STYLE=Manual", "ENABLE_HARDENED_RUNTIME=YES",
                        "OTHER_CODE_SIGN_FLAGS=--timestamp", "ENABLE_DEBUG_DYLIB=NO",
                        "CODE_SIGN_INJECT_BASE_ENTITLEMENTS=NO"])
    settings_command = ["xcodebuild", "-project", str(xcode_root / "cie-pkcs11.xcodeproj"),
                       "-scheme", "CIE ID", "-configuration", args.configuration,
                       "CIE_NATIVE_ARCH=" + args.arch, "ARCHS=" + args.arch, *signing]
    settings = json.loads(subprocess.check_output(
        [*settings_command, "-showBuildSettings", "-json"], text=True))
    app_settings = next(item["buildSettings"] for item in settings if item["target"] == "CIE ID")
    team = app_settings.get("DEVELOPMENT_TEAM", "")
    if signed and (not team or not app_settings.get("CIE_APP_GROUP_ID", "").startswith(team + ".")):
        raise RuntimeError("Development signing requires a team and a macOS team-prefixed app group")
    run("xcodebuild", "-project", xcode_root / "cie-pkcs11.xcodeproj", "-scheme", "CIE ID",
        "-configuration", args.configuration, "-derivedDataPath", derived,
        "CIE_NATIVE_ARCH=" + args.arch, "ARCHS=" + args.arch, *signing,
        *(["clean", "build"] if args.clean else ["build"]))
    app = derived / "Build/Products" / args.configuration / "CIE ID.app"
    found = []
    for file in sorted(app.rglob("*")):
        if file.is_file() and not file.is_symlink():
            description = subprocess.check_output(["file", "-b", file], text=True)
            if "Mach-O" in description:
                verify_binary(file, args.arch)
                found.append(file)
    if len(found) < 4:
        raise RuntimeError("Missing native executables or embedded middleware")
    middleware = app / "Contents/Frameworks/libcie-pkcs11.dylib"
    extension_middleware = app / "Contents/PlugIns/CIEToken.appex/Contents/Frameworks/libcie-pkcs11.dylib"
    if not signed and middleware.read_bytes() != extension_middleware.read_bytes():
        raise RuntimeError("The app and extension embed different middleware builds")
    for module in [middleware, extension_middleware]:
        run(build / "cie_middleware_tests", module)
    manifest = json.loads((ROOT / "scripts/license-manifest.json").read_text())
    for bundle in [app, app / "Contents/PlugIns/CIEToken.appex"]:
        resources = bundle / "Contents/Resources"
        for entry in manifest["license_files"]:
            notice = resources / entry["path"]
            if not notice.is_file() or hashlib.sha256(notice.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Missing or stale bundled licence: {notice}. Rebuild with --clean.")
        for name in ["THIRD_PARTY_NOTICES.md", "LICENSE_AUDIT.md"]:
            notice = resources / name
            if not notice.is_file() or notice.read_bytes() != (ROOT / name).read_bytes():
                raise RuntimeError(f"Missing or stale bundled notice: {notice}. Rebuild with --clean.")
    print(f"Verified {len(found)} native Mach-O files: {app}")
    if signed:
        verify_signature(app, found, team, developer_id=args.sign_developer_id)
    if source_fingerprints() != source_snapshot:
        raise RuntimeError("Source files changed during the build; rebuild before preparing release material")
    if (local_signing.read_bytes() if local_signing.exists() else None) != local_settings:
        raise RuntimeError("Local signing settings changed during the build; rebuild")
    exported = export_app(app, args.arch, variant)
    if signed:
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", exported)
    print("Exported app for Finder: " + str(exported))
    receipt = ROOT / ".build/publication" / (variant or "") / (args.arch + "-build.json")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({
        "source_files": source_snapshot,
        "application": str(exported.relative_to(ROOT)),
        "application_files": app_fingerprints(exported),
        "build_environment": {
            "architecture": args.arch, "macos": platform.mac_ver()[0],
            "xcode": subprocess.check_output(["xcodebuild", "-version"], text=True).strip(),
            "cmake": subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0],
            "deployment_target": "12.0", "signed": signed,
            "signing_kind": "developer-id" if args.sign_developer_id else "development" if signed else "unsigned",
            "configuration": args.configuration,
            "identity_settings": {key: app_settings.get(key, "") for key in
                                  ["DEVELOPMENT_TEAM", "CIE_BUNDLE_ID", "CIE_APP_GROUP_ID"]},
            "command": ["python3", "scripts/build-native-app.py", *sys.argv[1:]],
        },
    }, indent=2) + "\n")
    workspace_holder.cleanup()
    if not signed:
        print("Build verification completed without code signing; CryptoTokenKit activation requires a signed build.")


if __name__ == "__main__":
    main()
