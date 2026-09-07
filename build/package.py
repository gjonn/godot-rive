#!/usr/bin/env python3
"""Validate native installs and assemble one complete, directly extractable addon."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import tempfile
import zipfile

from build import install_descriptor

PLATFORMS = {"macos": (".arm64", "dylib"), "ios": ("", "xcframework"),
             "windows": (".x86_64", "dll")}
LICENSES = ("rive_surface", "godot_cpp", "rive_runtime", "rive_renderer",
            "harfbuzz", "sheenbidi", "yoga")


def library_names(platform):
    arch, extension = PLATFORMS[platform]
    return [f"librive_surface.{platform}.template_{target}{arch}.{extension}"
            for target in ("debug", "release")]


def require_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty package file: {path}")


def verify(addon, platform, load=False):
    require_file(addon / "README.md")
    require_file(addon / "rive_surface.gdextension")
    for license_name in LICENSES:
        require_file(addon / "licenses" / f"{license_name}.txt")
    for name in library_names(platform):
        path = addon / "bin" / name
        if platform == "ios":
            require_file(path / "Info.plist")
            info = plistlib.loads((path / "Info.plist").read_bytes())
            slices = info.get("AvailableLibraries", [])
            if not slices or not any("SupportedPlatformVariant" not in s for s in slices):
                raise ValueError(f"Missing iOS device slice: {path}")
            for item in slices:
                if item["SupportedPlatform"] != "ios" or item["SupportedArchitectures"] != ["arm64"]:
                    raise ValueError(f"Unexpected XCFramework slice: {item}")
                archive = path / item["LibraryIdentifier"] / item["LibraryPath"]
                if not archive.resolve().is_relative_to(path.resolve()):
                    raise ValueError(f"Archive outside XCFramework: {archive}")
                require_file(archive)
        else:
            require_file(path)
            if load:
                library = ctypes.CDLL(str(path.resolve()))
                getattr(library, "rive_surface_init")
        if f'"bin/{name}"' not in (addon / "rive_surface.gdextension").read_text():
            raise ValueError(f"Descriptor does not reference {name}")


def bundle(inputs, output, revision):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rive-bundle-") as temporary:
        root = Path(temporary)
        addon = root / "addons/rive"
        for platform in PLATFORMS:
            source = inputs / f"internal-{platform}"
            verify(source, platform)
            # Never silently overwrite a different README or license from another job.
            for path in sorted(source.rglob("*")):
                if not path.is_file() or path.name == "rive_surface.gdextension":
                    continue
                relative = path.relative_to(source)
                if relative.parts[0] not in ("bin", "licenses") and relative != Path("README.md"):
                    raise ValueError(f"Unexpected install file: {relative}")
                target = addon / relative
                if target.exists() and target.read_bytes() != path.read_bytes():
                    raise ValueError(f"Conflicting package file: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        install_descriptor(addon)
        for platform in PLATFORMS:
            verify(addon, platform)
        actual = {p.name for p in (addon / "bin").iterdir()}
        expected = {name for platform in PLATFORMS for name in library_names(platform)}
        if actual != expected:
            raise ValueError(f"Unexpected library inventory: {actual ^ expected}")
        files = {p.relative_to(addon).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(addon.rglob("*")) if p.is_file()}
        (addon / "build_manifest.json").write_text(json.dumps({
            "source_revision": revision, "platforms": list(PLATFORMS), "sha256": files,
        }, indent=2) + "\n", encoding="utf-8")
        archive = output / "rive-addon-all-platforms.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    package.write(path, path.relative_to(root).as_posix())
        with zipfile.ZipFile(archive) as package:
            if package.testzip() is not None:
                raise ValueError("ZIP integrity check failed")
        print(f"Created {archive} ({archive.stat().st_size:,} bytes)")
        return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--platform", choices=PLATFORMS, required=True)
    check.add_argument("--addon", type=Path, required=True)
    check.add_argument("--load", action="store_true")
    pack = commands.add_parser("bundle")
    pack.add_argument("--inputs", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--revision", required=True)
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.addon, args.platform, args.load)
    else:
        bundle(args.inputs, args.output, args.revision)
