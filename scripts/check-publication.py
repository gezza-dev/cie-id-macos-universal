#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check publication notices and report unresolved source/binary licence issues."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import platform
from publication_materials import app_fingerprints, sha256, source_fingerprints

ROOT = Path(__file__).resolve().parents[1]


def declared_license(text):
    if "GNU Lesser General Public License" in text or "GNU Library General Public License" in text:
        return "LGPL-2.0-or-later"
    if "GNU General Public License" in text:
        return "GPL-2.0-or-later"
    if "J.S.A.Kapp" in text:
        return "RSAEURO-unresolved"
    if "Paul E. Jones" in text:
        return "SHA1-unresolved"
    if "Royal Institute of Technology" in text:
        return "BSD-3-Clause-KTH"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    gate = parser.add_mutually_exclusive_group()
    gate.add_argument("--publish", action="store_true", help="Also require source publication issues to be resolved")
    gate.add_argument("--release", action="store_true", help="Also require source and binary release issues to be resolved")
    parser.add_argument("--arch", choices=["arm64", "x86_64", "universal2"], default=platform.machine())
    parser.add_argument("--variant", choices=["development", "release"], default="development")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "scripts/license-manifest.json").read_text())
    errors = []
    for lock, key in [("dependencies.lock.json", "dependencies"),
                      ("app-dependencies.lock.json", "app_dependencies")]:
        if json.loads((ROOT / "scripts" / lock).read_text()) != manifest[key]:
            errors.append(f"{lock} differs from the audited versions; refresh the audit")
    for entry in manifest["license_files"]:
        path = ROOT / entry["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append("Missing or changed licence text: " + entry["path"])
    paths = [entry["path"] for entry in manifest["license_files"]]
    if len(paths) != len(set(paths)):
        errors.append("The licence manifest contains duplicate paths")
    for asset in manifest.get("assets", []):
        path = ROOT / asset["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            errors.append("Changed licensed asset: " + asset["path"])
    if (ROOT / "LICENSE.txt").read_bytes() != (ROOT / "LICENSES/upstream/LICENSE.txt").read_bytes():
        errors.append("The original upstream LICENSE.txt has changed")
    inventory = json.loads((ROOT / "scripts/embedded-license-inventory.json").read_text())["files"]
    expected = {item["path"]: item["license"] for item in inventory}
    actual = {}
    for directory in ["cie-pkcs11", "cie_sign_sdk", "TestCIE"]:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix in [".c", ".cpp", ".h", ".hpp"] and "CMakeFiles" not in path.parts:
                kind = declared_license(path.read_text(errors="replace")[:3500])
                if kind:
                    actual[str(path.relative_to(ROOT))] = kind
    for name, kind in actual.items():
        if kind == "GPL-2.0-or-later" and name != "TestCIE/main.cpp":
            errors.append("Unexpected GPL code in production source: " + name)
        if kind in ["RSAEURO-unresolved", "SHA1-unresolved"]:
            errors.append("Unresolved legacy source restored: " + name)
    replacements = json.loads((ROOT / "scripts/replaced-legacy-sources.json").read_text())["files"]
    for item in replacements:
        path = ROOT / item["path"]
        if item["action"] == "removed" and path.exists():
            errors.append("Removed legacy implementation restored: " + item["path"])
        elif item["action"] == "reimplemented" and (not path.is_file() or
                "SPDX-License-Identifier: BSD-3-Clause" not in path.read_text()):
            errors.append("Missing BSD replacement: " + item["path"])
    if actual != expected:
        errors.append("The embedded licence inventory differs from the source notices; review the inventory")
    removed = json.loads((ROOT / "scripts/removed-upstream-artifacts.json").read_text())["artifacts"]
    for item in removed:
        if (ROOT / item["path"]).exists():
            errors.append("Unused upstream build artefact was restored: " + item["path"])
    old_headers = json.loads((ROOT / "scripts/removed-legacy-openssl-headers.json").read_text())["files"]
    for item in old_headers:
        if (ROOT / item["path"]).exists():
            errors.append("Obsolete vendored OpenSSL header restored: " + item["path"])
    for required in ["README.md", "THIRD_PARTY_NOTICES.md", "LICENSE_AUDIT.md", "Docs/PUBLICATION.md", "Docs/REBUILDING.md"]:
        if not (ROOT / required).is_file():
            errors.append("Missing publication document: " + required)
    issues = manifest["issues"]
    for issue in issues:
        if issue["status"] == "resolved" and not issue.get("resolution"):
            errors.append("A resolved issue needs documented evidence: " + issue["id"])
    if args.release:
        receipt = ROOT / ".build/publication" / ("release" if args.variant == "release" else "") / (args.arch + "-source-package.json")
        try:
            material = json.loads(receipt.read_text())
            package = ROOT / material["package"]
            if not package.is_file() or sha256(package) != material["package_sha256"]:
                errors.append("Missing or changed corresponding-source package")
            if source_fingerprints(ROOT) != material["source_files"]:
                errors.append("Source changed after packaging; rebuild app and corresponding sources")
            app = ROOT / material["application"]
            if not app.is_dir() or app_fingerprints(app) != material["application_files"]:
                errors.append("Application changed after packaging; rebuild/re-sign and regenerate sources")
        except (OSError, KeyError, ValueError, RuntimeError) as error:
            errors.append("Matching source package required: run prepare-source-package.py after building (" + str(error) + ")")
    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1
    print(f"Verified {len(manifest['license_files'])} licence texts and {len(inventory)} embedded source notices.")
    unresolved = [issue for issue in issues if issue["status"] != "resolved"]
    for issue in unresolved:
        print(f"REVIEW {issue['id']} ({', '.join(issue['scopes'])}): {issue['summary']}")
    scope = "binary" if args.release else "source" if args.publish else None
    if scope and any(scope in issue["scopes"] or (args.release and "source" in issue["scopes"])
                     for issue in unresolved):
        print("Publication review is incomplete; see LICENSE_AUDIT.md.", file=sys.stderr)
        return 2
    print("Licence inventory checks passed" + ("; matching app/source package verified." if args.release else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
