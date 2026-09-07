#!/usr/bin/env python3
"""Build RiveSurface for macOS/iOS arm64 or Windows x86_64."""
import argparse
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "native"
LIBRARIES = ("rive", "rive_harfbuzz", "rive_sheenbidi", "rive_yoga", "rive_cg_renderer")


def run(command, **kwargs):
    subprocess.run([str(value) for value in command], check=True, **kwargs)


def build_ios(args, runtime, env, targets):
    variants = ("device", "simulator") if args.simulator else ("device",)
    for variant in variants:
        sdk = "iphonesimulator" if variant == "simulator" else "iphoneos"
        run(["xcrun", "--sdk", sdk, "--show-sdk-path"])
        runtime_env = env.copy()
        runtime_env["RIVE_OUT"] = f"out/ios_{variant}_release"
        runtime_env["RIVE_PREMAKE_ARGS"] += " --no-lto"
        run([runtime / "build/build_rive.sh", "arm64",
             "iossim" if variant == "simulator" else "ios", "release", "--", *LIBRARIES],
            cwd=BUILD, env=runtime_env)
        for target in targets:
            run([sys.executable, "-m", "SCons", "platform=ios", "arch=arm64",
                 f"ios_simulator={'yes' if variant == 'simulator' else 'no'}",
                 f"ios_min_version={args.ios_min_version}", f"target=template_{target}",
                 "build_profile=build_profile.json", f"-j{args.jobs}"], cwd=BUILD)
            cpp_suffix = ".simulator" if variant == "simulator" else ""
            archives = [BUILD / f"bin/librive_surface.ios.template_{target}.arm64.{variant}.a",
                        ROOT / f"godot-cpp/bin/libgodot-cpp.ios.template_{target}.arm64{cpp_suffix}.a"]
            archives += [BUILD / runtime_env["RIVE_OUT"] / f"lib{name}.a" for name in LIBRARIES]
            # A StaticLibrary target does not absorb its LIBS. Merge the entire
            # dependency closure so the app needs only this one XCFramework.
            run(["xcrun", "libtool", "-static", "-o",
                 BUILD / f"bin/librive_surface.ios.template_{target}.{variant}.a", *archives])
    for target in targets:
        output = BUILD / f"bin/librive_surface.ios.template_{target}.xcframework"
        if output.exists():
            shutil.rmtree(output)
        command = ["xcodebuild", "-create-xcframework"]
        for variant in variants:
            command += ["-library", BUILD / f"bin/librive_surface.ios.template_{target}.{variant}.a"]
        run([*command, "-output", output])
        verify_ios_framework(output, args.ios_min_version)


def verify_ios_framework(framework, minimum_version):
    """Link the actual entry point with only the packaged archive, never export an app."""
    info = plistlib.loads((framework / "Info.plist").read_bytes())
    with tempfile.TemporaryDirectory(prefix="rive-ios-link-") as folder:
        source = Path(folder) / "main.cpp"
        source.write_text("int main() { return 0; }\n")
        for library in info["AvailableLibraries"]:
            if library["SupportedPlatform"] != "ios" or library["SupportedArchitectures"] != ["arm64"]:
                raise RuntimeError(f"Unexpected XCFramework slice: {library}")
            simulator = library.get("SupportedPlatformVariant") == "simulator"
            sdk_name = "iphonesimulator" if simulator else "iphoneos"
            sdk = subprocess.check_output(["xcrun", "--sdk", sdk_name, "--show-sdk-path"],
                                          text=True).strip()
            triple = f"arm64-apple-ios{minimum_version}" + ("-simulator" if simulator else "")
            archive = framework / library["LibraryIdentifier"] / library["LibraryPath"]
            run(["xcrun", "--sdk", sdk_name, "clang++", "-target", triple, "-isysroot", sdk,
                 source, "-Wl,-u,_rive_surface_init", archive, "-o", Path(folder) / "link_probe"])
            print(f"Verified iOS link: {framework.name} ({library['LibraryIdentifier']})", flush=True)


def install_descriptor(destination):
    # Installing one platform must preserve the others, and must not advertise
    # libraries that are absent in a fresh, single-platform installation.
    lines = ['[configuration]', 'entry_symbol = "rive_surface_init"',
             'compatibility_minimum = "4.7"', 'reloadable = false', '', '[libraries]']
    for platform_name, extension, arch in (("macos", "dylib", ".arm64"),
                                           ("ios", "xcframework", ""),
                                           ("windows", "dll", ".x86_64")):
        for target in ("debug", "release"):
            name = f"librive_surface.{platform_name}.template_{target}{arch}.{extension}"
            if (destination / "bin" / name).exists():
                tag = f"{platform_name}.{target}" + arch
                lines.append(f'{tag} = "bin/{name}"')
    (destination / "rive_surface.gdextension").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("both", "debug", "release"), default="both")
    parser.add_argument("--platform", choices=("macos", "ios", "windows"),
                        default="windows" if platform.system() == "Windows" else "macos")
    parser.add_argument("--simulator", action="store_true", help="Include an iOS arm64 simulator slice.")
    parser.add_argument("--ios-min-version", default="15.0")
    parser.add_argument("--jobs", "-j", type=int, default=min(os.cpu_count() or 4, 8))
    parser.add_argument("--install", type=Path, help="Copy the built addon to this directory.")
    args = parser.parse_args()
    if args.platform == "windows":
        if platform.system() != "Windows" or platform.machine().lower() not in ("amd64", "x86_64"):
            parser.error("The Windows backend requires an x64 Windows build host.")
    elif platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("Apple targets require a macOS arm64 build host.")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.simulator and args.platform != "ios":
        parser.error("--simulator requires --platform ios")
    if args.install and args.target != "both":
        parser.error("--install requires both debug and release builds")
    runtime = ROOT / "thirdparty" / "rive-cpp"
    if not (runtime / "build" / "build_rive.sh").is_file():
        parser.error("Initialize the pinned submodules: git submodule update --init --recursive")
    env = os.environ.copy()
    env["RIVE_PREMAKE_ARGS"] = "--with_rive_text --with_rive_layout"
    targets = ("debug", "release") if args.target == "both" else (args.target,)
    if args.platform == "windows":
        import windows
        windows.build(args, ROOT, BUILD, targets)
    elif args.platform == "ios":
        build_ios(args, runtime, env, targets)
    else:
        run([runtime / "build/build_rive.sh", "release", "--", *LIBRARIES], cwd=BUILD, env=env)
        for target in targets:
            run([sys.executable, "-m", "SCons", "platform=macos", "arch=arm64",
                 f"target=template_{target}", "build_profile=build_profile.json", f"-j{args.jobs}"],
                cwd=BUILD)
    if args.install:
        destination = args.install.resolve()
        (destination / "bin").mkdir(parents=True, exist_ok=True)
        (destination / "licenses").mkdir(exist_ok=True)
        for target in targets:
            if args.platform == "ios":
                name = f"librive_surface.ios.template_{target}.xcframework"
                if (destination / "bin" / name).exists():
                    shutil.rmtree(destination / "bin" / name)
                shutil.copytree(BUILD / "bin" / name, destination / "bin" / name)
            else:
                name = (f"librive_surface.windows.template_{target}.x86_64.dll"
                        if args.platform == "windows" else
                        f"librive_surface.macos.template_{target}.arm64.dylib")
                # A loaded Mach-O must get a new inode. In-place replacement can
                # leave macOS's code-signature page cache attached to old bytes.
                temporary = destination / "bin" / f"{name}.installing"
                shutil.copy2(BUILD / "bin" / name, temporary)
                os.replace(temporary, destination / "bin" / name)
        install_descriptor(destination)
        shutil.copy2(ROOT / "native" / "README.md", destination / "README.md")
        licenses = {
            ROOT / "native" / "LICENSE": "rive_surface.txt",
            ROOT / "godot-cpp" / "LICENSE.md": "godot_cpp.txt",
            runtime / "LICENSE": "rive_runtime.txt",
            runtime / "renderer/LICENSE": "rive_renderer.txt",
            BUILD / "dependencies/rive-app_harfbuzz_rive_13.1.1/COPYING": "harfbuzz.txt",
            BUILD / "dependencies/Tehreer_SheenBidi_v2.6/LICENSE": "sheenbidi.txt",
            BUILD / "dependencies/rive-app_yoga_rive_changes_v2_0_1_3_grid/LICENSE": "yoga.txt",
        }
        for source, name in licenses.items():
            shutil.copy2(source, destination / "licenses" / name)
        print(f"Installed RiveSurface in {destination}")


if __name__ == "__main__":
    main()
