import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import install_descriptor
from package import LICENSES, PLATFORMS, bundle, library_names


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        for platform in PLATFORMS:
            addon = self.inputs / f"internal-{platform}"
            (addon / "bin").mkdir(parents=True)
            (addon / "licenses").mkdir()
            (addon / "README.md").write_text("Install instructions")
            for name in LICENSES:
                (addon / "licenses" / f"{name}.txt").write_text(name)
            for name in library_names(platform):
                path = addon / "bin" / name
                if platform == "ios":
                    (path / "ios-arm64").mkdir(parents=True)
                    (path / "ios-arm64/rive.a").write_bytes(b"test archive")
                    (path / "Info.plist").write_bytes(plistlib.dumps({"AvailableLibraries": [{
                        "SupportedPlatform": "ios", "SupportedArchitectures": ["arm64"],
                        "LibraryIdentifier": "ios-arm64", "LibraryPath": "rive.a",
                    }]}))
                else:
                    path.write_bytes(b"test library")
            install_descriptor(addon)

    def test_complete_bundle_extracts_with_all_descriptor_paths_and_hashes(self):
        archive = bundle(self.inputs, self.root / "dist", "test-revision")
        with zipfile.ZipFile(archive) as package:
            package.extractall(self.root / "installed")
        addon = self.root / "installed/addons/rive"
        descriptor = (addon / "rive_surface.gdextension").read_text()
        for platform in PLATFORMS:
            for name in library_names(platform):
                self.assertIn(f'"bin/{name}"', descriptor)
                self.assertTrue((addon / "bin" / name).exists())
        import hashlib
        manifest = json.loads((addon / "build_manifest.json").read_text())
        self.assertEqual(manifest["source_revision"], "test-revision")
        for relative, digest in manifest["sha256"].items():
            self.assertEqual(hashlib.sha256((addon / relative).read_bytes()).hexdigest(), digest)

    def test_missing_release_library_fails(self):
        (self.inputs / "internal-windows/bin" / library_names("windows")[1]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing or empty"):
            bundle(self.inputs, self.root / "dist", "test")

    def test_missing_ios_archive_fails(self):
        (self.inputs / "internal-ios/bin" / library_names("ios")[0] / "ios-arm64/rive.a").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or empty"):
            bundle(self.inputs, self.root / "dist", "test")

    def test_conflicting_licenses_fail(self):
        (self.inputs / "internal-windows/licenses/rive_runtime.txt").write_text("different license")
        with self.assertRaisesRegex(ValueError, "Conflicting package file"):
            bundle(self.inputs, self.root / "dist", "test")

    def test_unexpected_library_fails(self):
        (self.inputs / "internal-windows/bin/stale.dll").write_bytes(b"stale")
        with self.assertRaisesRegex(ValueError, "Unexpected library inventory"):
            bundle(self.inputs, self.root / "dist", "test")


if __name__ == "__main__":
    unittest.main()
