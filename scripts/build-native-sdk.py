#!/usr/bin/env python3
"""Build native dependencies, compile and test the signing SDK, then stage it."""
import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default=platform.machine())
    parser.add_argument("--deployment-target", default="12.0")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 6))
    args = parser.parse_args()
    subprocess.run([sys.executable, ROOT / "scripts/build-dependencies.py", "--arch", args.arch,
                    "--deployment-target", args.deployment_target, "--jobs", str(args.jobs)], check=True)
    build = ROOT / ".build/sign-sdk" / args.arch
    prefix = ROOT / ".build/dependencies" / args.arch / "prefix"
    subprocess.run(["cmake", "-S", ROOT / "cie_sign_sdk", "-B", build,
                    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=" + args.arch,
                    "-DCMAKE_OSX_DEPLOYMENT_TARGET=" + args.deployment_target,
                    "-DCIE_DEPENDENCY_PREFIX=" + str(prefix),
                    "-DCMAKE_INSTALL_PREFIX=" + str(build / "install"), "-DCIE_BUILD_TESTS=ON"], check=True)
    subprocess.run(["cmake", "--build", build, "--parallel", str(args.jobs)], check=True)
    subprocess.run(["ctest", "--test-dir", build, "--output-on-failure"], check=True)
    executable = build / "cie_sdk_tests"
    if subprocess.check_output(["lipo", "-archs", executable], text=True).split() != [args.arch]:
        raise RuntimeError("Unexpected test executable architecture")
    imports = subprocess.check_output(["otool", "-L", executable], text=True).splitlines()[1:]
    for imported in imports:
        path = imported.strip().split(" (", 1)[0]
        if not path.startswith(("/System/Library/", "/usr/lib/")):
            raise RuntimeError("Non-system dynamic dependency: " + path)
    subprocess.run(["cmake", "--install", build], check=True)
    archive = build / "install/lib/libcie_sign_sdk.a"
    architectures = subprocess.check_output(["lipo", "-archs", archive], text=True).split()
    if architectures != [args.arch]:
        raise RuntimeError("Unexpected SDK architecture: " + str(architectures))
    print("Verified SDK: " + str(archive))


if __name__ == "__main__":
    main()
