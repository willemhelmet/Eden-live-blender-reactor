#!/usr/bin/env python3
"""Build the installable extension zip.

    python tools/build_extension.py --blender /path/to/blender

1. Downloads the reactor-sdk wheels listed in blender_manifest.toml from PyPI
   (sha256-verified) into eden_live_previs/wheels/.
2. Runs ``blender --command extension build`` -> dist/eden_live_previs-<version>.zip,
   one zip for every platform. It carries all four wheels (about 10 MB each);
   Blender installs only the wheel that matches the machine it is installed on.

Options:
  --legacy        also write dist/eden_live_previs-<version>-legacy-addon.zip, the
                  add-on without wheels for "Install from Disk" as a legacy add-on
                  (the SDK is then installed from the add-on preferences).
  --skip-blender  only fetch wheels (and build the legacy zip with --legacy).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "eden_live_previs")
MANIFEST = os.path.join(ADDON, "blender_manifest.toml")
DIST = os.path.join(ROOT, "dist")


def manifest_wheels():
    text = open(MANIFEST, encoding="utf-8").read()
    return re.findall(r'"\./wheels/([^"]+\.whl)"', text)


def manifest_version():
    return re.search(r'^version\s*=\s*"([^"]+)"', open(MANIFEST, encoding="utf-8").read(), re.M).group(1)


def fetch_wheels():
    wanted = manifest_wheels()
    versions = {re.match(r"reactor_sdk-([^-]+)-", w).group(1) for w in wanted}
    if len(versions) != 1:
        sys.exit(f"manifest lists mixed reactor-sdk versions: {versions}")
    version = versions.pop()
    with urllib.request.urlopen(f"https://pypi.org/pypi/reactor-sdk/{version}/json") as resp:
        files = {f["filename"]: f for f in json.load(resp)["urls"]}
    out_dir = os.path.join(ADDON, "wheels")
    os.makedirs(out_dir, exist_ok=True)
    for name in wanted:
        if name not in files:
            sys.exit(f"{name} is not published on PyPI")
        info = files[name]
        path = os.path.join(out_dir, name)
        if os.path.exists(path) and hashlib.sha256(open(path, "rb").read()).hexdigest() == info["digests"]["sha256"]:
            print(f"ok      {name}")
            continue
        print(f"fetch   {name}")
        with urllib.request.urlopen(info["url"]) as resp:
            data = resp.read()
        if hashlib.sha256(data).hexdigest() != info["digests"]["sha256"]:
            sys.exit(f"sha256 mismatch for {name}")
        with open(path, "wb") as f:
            f.write(data)


def build_extension(blender):
    os.makedirs(DIST, exist_ok=True)
    path = os.path.join(DIST, f"eden_live_previs-{manifest_version()}.zip")
    cmd = [blender, "--factory-startup", "--command", "extension", "build",
           "--source-dir", ADDON, "--output-filepath", path]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    subprocess.run([blender, "--factory-startup", "--command", "extension", "validate", path], check=True)
    with zipfile.ZipFile(path) as zf:
        wheels = [n for n in zf.namelist() if n.endswith(".whl")]
    missing = set(manifest_wheels()) - {os.path.basename(w) for w in wheels}
    if missing:
        sys.exit(f"{path} is missing wheels: {sorted(missing)}")
    print(f"wrote   {path} ({os.path.getsize(path) / 1e6:.1f} MB, {len(wheels)} wheels)")
    return path


def build_legacy():
    os.makedirs(DIST, exist_ok=True)
    path = os.path.join(DIST, f"eden_live_previs-{manifest_version()}-legacy-addon.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, dirs, files in os.walk(ADDON):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "wheels")]
            for name in files:
                if name.endswith((".pyc", ".whl")):
                    continue
                full = os.path.join(base, name)
                zf.write(full, os.path.join("eden_live_previs", os.path.relpath(full, ADDON)))
    print(f"wrote   {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blender", default=shutil.which("blender") or "blender")
    parser.add_argument("--skip-blender", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="also build the legacy add-on zip (no wheels)")
    args = parser.parse_args()
    fetch_wheels()
    if not args.skip_blender:
        build_extension(args.blender)
    if args.legacy:
        build_legacy()


if __name__ == "__main__":
    main()
