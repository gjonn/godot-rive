#!/usr/bin/env python3
"""Build the maintained Godot 4.7 RiveSurface backend (macOS arm64)."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "native"
LIBRARIES = ("rive", "rive_harfbuzz", "rive_sheenbidi", "rive_yoga", "rive_cg_renderer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("both", "debug", "release"), default="both")
    parser.add_argument("--jobs", "-j", type=int, default=min(os.cpu_count() or 4, 8))
    parser.add_argument("--install", type=Path, help="Copy the built addon to this directory.")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This backend currently builds on macOS arm64 only.")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.install and args.target != "both":
        parser.error("--install requires both debug and release builds")
    runtime = ROOT / "thirdparty" / "rive-cpp"
    if not (runtime / "build" / "build_rive.sh").is_file():
        parser.error("Initialize the pinned submodules: git submodule update --init --recursive")
    env = os.environ.copy()
    env["RIVE_PREMAKE_ARGS"] = "--with_rive_text --with_rive_layout"
    subprocess.run([str(runtime / "build" / "build_rive.sh"), "release", "--", *LIBRARIES],
                   cwd=BUILD, env=env, check=True)
    targets = ("debug", "release") if args.target == "both" else (args.target,)
    for target in targets:
        subprocess.run([sys.executable, "-m", "SCons", "platform=macos", "arch=arm64",
                        f"target=template_{target}", "build_profile=build_profile.json",
                        f"-j{args.jobs}"], cwd=BUILD, check=True)
    if args.install:
        destination = args.install.resolve()
        (destination / "bin").mkdir(parents=True, exist_ok=True)
        (destination / "licenses").mkdir(exist_ok=True)
        for target in targets:
            name = f"librive_surface.macos.template_{target}.arm64.dylib"
            shutil.copy2(BUILD / "bin" / name, destination / "bin" / name)
        shutil.copy2(BUILD / "rive_surface.gdextension", destination)
        shutil.copy2(ROOT / "native" / "README.md", destination / "README.md")
        licenses = {
            ROOT / "native" / "LICENSE": "rive_surface.txt",
            ROOT / "godot-cpp" / "LICENSE.md": "godot_cpp.txt",
            runtime / "LICENSE": "rive_runtime.txt",
            BUILD / "dependencies/rive-app_harfbuzz_rive_13.1.1/COPYING": "harfbuzz.txt",
            BUILD / "dependencies/Tehreer_SheenBidi_v2.6/LICENSE": "sheenbidi.txt",
            BUILD / "dependencies/rive-app_yoga_rive_changes_v2_0_1_3_grid/LICENSE": "yoga.txt",
        }
        for source, name in licenses.items():
            shutil.copy2(source, destination / "licenses" / name)
        print(f"Installed RiveSurface in {destination}")


if __name__ == "__main__":
    main()
