#!/usr/bin/env python3
"""Build checksum-pinned macOS static dependencies in an isolated prefix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "scripts/dependencies.lock.json").read_text())
ORDER = ["openssl", "cryptopp", "zlib", "bzip2", "libiconv", "expat",
         "libpng", "freetype", "fontconfig", "libxml2", "libcurl", "podofo"]
ARCHIVES = ["crypto", "ssl", "cryptopp", "z", "bz2", "iconv", "charset",
            "expat", "png16", "freetype", "fontconfig", "xml2", "curl", "podofo"]


def run(command, cwd, env, log):
    log.write("\n$ " + shlex.join([str(x) for x in command]) + "\n")
    log.flush()
    subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                   stdout=log, stderr=subprocess.STDOUT, check=True)


def unpack(archive, destination):
    # Reject traversal and links escaping the source tree, including on Python 3.9.
    with tarfile.open(archive) as tar:
        root = destination.resolve()
        members = tar.getmembers()
        for member in members:
            target = (root / member.name).resolve()
            if not target.is_relative_to(root) or member.isdev():
                raise ValueError("Unsafe archive member: " + member.name)
            if member.issym() or member.islnk():
                base = target.parent if member.issym() else root
                if not (base / member.linkname).resolve().is_relative_to(root):
                    raise ValueError("Unsafe archive link: " + member.name)
        tar.extractall(root)
        return root / members[0].name.split("/")[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default=platform.machine())
    parser.add_argument("--deployment-target", default="12.0")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 6))
    parser.add_argument("--only", choices=ORDER, help="Build one dependency (prerequisites must exist)")
    parser.add_argument("--force", action="store_true", help="Rebuild selected dependencies")
    args = parser.parse_args()
    if platform.system() != "Darwin" or args.jobs < 1:
        parser.error("A macOS host and a positive job count are required")
    for tool in ["cmake", "make", "perl", "pkg-config", "xcrun", "lipo"]:
        if not shutil.which(tool):
            parser.error("Missing build tool: " + tool)

    work = ROOT / ".build/dependencies"
    build_root = work / args.arch
    prefix = build_root / "prefix"
    for path in [work / "downloads", build_root / "logs", prefix / "lib", prefix / "include"]:
        path.mkdir(parents=True, exist_ok=True)
    sdk = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
    env = os.environ.copy()
    flags = shlex.join(["-O2", "-fPIC", "-arch", args.arch, "-isysroot", sdk,
                        "-mmacosx-version-min=" + args.deployment_target])
    env.update(CC=subprocess.check_output(["xcrun", "--find", "clang"], text=True).strip(),
               CXX=subprocess.check_output(["xcrun", "--find", "clang++"], text=True).strip(),
               CFLAGS=flags, CXXFLAGS=flags + " -std=c++11", CPPFLAGS="-I" + shlex.quote(str(prefix / "include")),
               LDFLAGS=flags + " -L" + shlex.quote(str(prefix / "lib")),
               PKG_CONFIG_LIBDIR=os.pathsep.join([str(prefix / "lib/pkgconfig"), str(prefix / "share/pkgconfig")]), PKG_CONFIG_PATH="",
               MACOSX_DEPLOYMENT_TARGET=args.deployment_target, SDKROOT=sdk)
    recipe_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    compiler = subprocess.check_output([env["CC"], "--version"], text=True).splitlines()[0]
    sdk_version = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-version"], text=True).strip()

    def cmake(source, build, options, log):
        # Prevent optional libraries from silently linking to Homebrew dylibs.
        run(["cmake", "-S", source, "-B", build,
             "-DCMAKE_POLICY_VERSION_MINIMUM=3.5", "-DCMAKE_BUILD_TYPE=Release",
             "-DCMAKE_OSX_ARCHITECTURES=" + args.arch,
             "-DCMAKE_OSX_DEPLOYMENT_TARGET=" + args.deployment_target,
             "-DCMAKE_OSX_SYSROOT=" + sdk, "-DCMAKE_INSTALL_PREFIX=" + str(prefix),
             "-DCMAKE_INSTALL_LIBDIR=lib", "-DCMAKE_PREFIX_PATH=" + str(prefix),
             "-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local",
             "-DCMAKE_FIND_FRAMEWORK=LAST",
             "-DBUILD_SHARED_LIBS=OFF", "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
             *options], ROOT, env, log)
        run(["cmake", "--build", build, "--parallel", args.jobs], ROOT, env, log)
        run(["cmake", "--install", build], ROOT, env, log)

    for name in [args.only] if args.only else ORDER:
        item = LOCK[name]
        stamp = build_root / (name + ".json")
        identity = dict(source=item, arch=args.arch, deployment_target=args.deployment_target,
                        recipe_hash=recipe_hash, compiler=compiler, sdk_version=sdk_version,
                        openssl_source=LOCK["openssl"] if name in ["libcurl", "podofo"] else None)
        if not args.force and stamp.exists() and json.loads(stamp.read_text()) == identity:
            print("Already built: " + name, flush=True)
            continue
        archive = work / "downloads" / item["archive"]
        if not archive.exists():
            print("Downloading " + name, flush=True)
            temporary = archive.with_suffix(archive.suffix + ".part")
            with urllib.request.urlopen(item["url"], timeout=60) as response, temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            temporary.replace(archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Checksum mismatch: " + str(archive))
        source_root = build_root / "sources" / name
        shutil.rmtree(source_root, ignore_errors=True)
        source_root.mkdir(parents=True)
        source = unpack(archive, source_root)
        build = build_root / "build" / name
        shutil.rmtree(build, ignore_errors=True)
        build.mkdir(parents=True)
        log_path = build_root / "logs" / (name + ".log")
        print("Building " + name + " " + item["version"] + " for " + args.arch + " (" + str(log_path) + ")", flush=True)
        try:
            with log_path.open("w") as log:
                if name == "openssl":
                    target = "darwin64-" + ("arm64" if args.arch == "arm64" else "x86_64") + "-cc"
                    run(["perl", source / "Configure", target, "no-shared", "no-module", "no-autoload-config", "no-tests", "no-asm",
                         "--prefix=" + str(prefix), "--openssldir=" + str(prefix / "ssl")], build, env, log)
                    run(["make", "-j" + str(args.jobs)], build, env, log)
                    run(["make", "install_sw"], build, env, log)
                elif name == "cryptopp":
                    run(["make", "-j" + str(args.jobs), "libcryptopp.a", "CXX=" + env["CXX"],
                         "IS_ARM32=0", "CXXFLAGS=" + flags + " -std=c++11 -DCRYPTOPP_DISABLE_ASM"], source, env, log)
                    shutil.copy2(source / "libcryptopp.a", prefix / "lib")
                    headers = prefix / "include/cryptopp"
                    headers.mkdir(exist_ok=True)
                    for header in source.glob("*.h"):
                        shutil.copy2(header, headers)
                elif name == "bzip2":
                    run(["make", "-j" + str(args.jobs), "libbz2.a", "CC=" + env["CC"], "CFLAGS=" + flags], source, env, log)
                    shutil.copy2(source / "libbz2.a", prefix / "lib")
                    shutil.copy2(source / "bzlib.h", prefix / "include")
                elif name in ["libiconv", "fontconfig"]:
                    options = ["--enable-static", "--disable-shared"]
                    if name == "libiconv":
                        options += ["--disable-nls"]
                    else:
                        options += ["--disable-docs", "--disable-nls", "--disable-cache-build",
                                    "--with-add-fonts=/System/Library/Fonts,/Library/Fonts"]
                    run([source / "configure", "--prefix=" + str(prefix),
                         "--host=" + ("aarch64" if args.arch == "arm64" else "x86_64") + "-apple-darwin", *options], build, env, log)
                    run(["make", "-j" + str(args.jobs)], build, env, log)
                    run(["make", "install"], build, env, log)
                elif name == "zlib":
                    cmake(source, build, ["-DZLIB_BUILD_EXAMPLES=OFF"], log)
                    # zlib's older CMake builds both variants even with BUILD_SHARED_LIBS=OFF.
                    for dynamic in (prefix / "lib").glob("libz*.dylib"):
                        dynamic.unlink()
                elif name == "expat":
                    cmake(source / "expat", build, ["-DEXPAT_SHARED_LIBS=OFF", "-DEXPAT_BUILD_TESTS=OFF",
                          "-DEXPAT_BUILD_EXAMPLES=OFF", "-DEXPAT_BUILD_TOOLS=OFF", "-DEXPAT_BUILD_DOCS=OFF"], log)
                elif name == "libpng":
                    shutil.rmtree(prefix / "lib/png.framework", ignore_errors=True)
                    cmake(source, build, ["-DPNG_SHARED=OFF", "-DPNG_FRAMEWORK=OFF", "-DPNG_TESTS=OFF", "-DPNG_TOOLS=OFF"], log)
                elif name == "freetype":
                    cmake(source, build, ["-DFT_DISABLE_HARFBUZZ=ON", "-DFT_DISABLE_BROTLI=ON"], log)
                elif name == "libxml2":
                    cmake(source, build, ["-DLIBXML2_WITH_PYTHON=OFF", "-DLIBXML2_WITH_PROGRAMS=OFF",
                          "-DLIBXML2_WITH_TESTS=OFF", "-DLIBXML2_WITH_LZMA=OFF", "-DLIBXML2_WITH_ICU=OFF"], log)
                elif name == "libcurl":
                    cmake(source, build, ["-DBUILD_CURL_EXE=OFF", "-DBUILD_TESTING=OFF",
                          "-DCURL_USE_OPENSSL=ON", "-DOPENSSL_ROOT_DIR=" + str(prefix),
                          "-DCURL_USE_LIBPSL=OFF", "-DCURL_USE_LIBSSH2=OFF", "-DUSE_NGHTTP2=OFF",
                          "-DCURL_BROTLI=OFF", "-DCURL_ZSTD=OFF", "-DUSE_LIBIDN2=OFF",
                          "-DCURL_USE_GSSAPI=OFF", "-DCURL_USE_SECTRANSP=OFF"], log)
                elif name == "podofo":
                    # PoDoFo 0.9.8 skips LIBCRYPTO_FOUND when both native paths
                    # are supplied. Validate these explicit paths with FPHSA;
                    # otherwise encryption is silently disabled despite OpenSSL.
                    module = source / "cmake/modules/FindLIBCRYPTO.cmake"
                    marker = b"# check whether using OpenSSL 1.1 API"
                    contents = module.read_bytes()
                    if contents.count(marker) != 1:
                        raise ValueError("Unexpected PoDoFo libcrypto detection source")
                    addition = (b"# Modified 2026-10-14 for native fork: validate explicit libcrypto paths.\r\n"
                                b"INCLUDE(FindPackageHandleStandardArgs)\r\n"
                                b"FIND_PACKAGE_HANDLE_STANDARD_ARGS(LIBCRYPTO DEFAULT_MSG "
                                b"LIBCRYPTO_INCLUDE_DIR LIBCRYPTO_LIBRARIES)\r\n\r\n")
                    module.write_bytes(contents.replace(marker, addition + marker))
                    cmake(source, build, ["-DPODOFO_BUILD_STATIC=ON", "-DPODOFO_BUILD_SHARED=OFF",
                          "-DPODOFO_BUILD_LIB_ONLY=ON", "-DCMAKE_CXX_STANDARD=11",
                          "-DCMAKE_DISABLE_FIND_PACKAGE_JPEG=ON", "-DCMAKE_DISABLE_FIND_PACKAGE_TIFF=ON",
                          "-DCMAKE_DISABLE_FIND_PACKAGE_LIBIDN=ON", "-DCMAKE_DISABLE_FIND_PACKAGE_LUA=ON",
                          "-DLIBCRYPTO_INCLUDE_DIR=" + str(prefix / "include"),
                          "-DLIBCRYPTO_LIBRARIES=" + str(prefix / "lib/libcrypto.a"),
                          "-DFREETYPE_INCLUDE_DIR_FT2BUILD=" + str(prefix / "include/freetype2"),
                          "-DFREETYPE_INCLUDE_DIR_FTHEADER=" + str(prefix / "include/freetype2"),
                          "-DFREETYPE_LIBRARY_RELEASE=" + str(prefix / "lib/libfreetype.a")], log)
        except subprocess.CalledProcessError:
            print(log_path.read_text()[-6000:], flush=True)
            raise SystemExit("Build failed: " + name + "; see " + str(log_path))
        stamp.write_text(json.dumps(identity, indent=2) + "\n")

    if not args.only:
        for name in ARCHIVES:
            path = prefix / "lib" / ("lib" + name + ".a")
            arches = subprocess.check_output(["lipo", "-archs", path], text=True).split()
            if arches != [args.arch]:
                raise ValueError("Unexpected architecture: " + str(path) + ": " + str(arches))
        (prefix / "cie-dependencies.json").write_text(json.dumps(dict(
            arch=args.arch, deployment_target=args.deployment_target, sources=LOCK), indent=2) + "\n")
        print("Verified static dependencies: " + str(prefix), flush=True)


if __name__ == "__main__":
    main()
