"""Build the pinned official Rive Canvas2D runtime with two host API bindings.

No Apple frameworks, Node packages, Java, scripting, audio, SIMD or threads are
required by the resulting browser binary. Upstream provisions Emscripten 4.0.23.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


REVISION = "5d6ba49123f149d46f848359efadcd1559eda000"


def run(*args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def install(root, destination):
    source = root / "web/addon"
    vendor = source / "web/vendor"
    receipt = json.loads((vendor / "build.json").read_text())
    for name, expected in receipt["sha256"].items():
        if hashlib.sha256((vendor / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Bundled runtime checksum mismatch: {name}")
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise RuntimeError("Install into a game addon directory, not the source package")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    shutil.copy2(root / "web/README.md", destination / "WEB_README.md")
    print(f"Installed web addon in {destination}; enable Rive Web Export in Godot")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, help="Rebuild in this dedicated checkout outside the repository")
    parser.add_argument("--install", type=Path, help="Install alongside native files in a Godot addons/rive directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.work is None:
        if args.install is None:
            parser.error("Provide --install to use the bundled runtime, or --work to rebuild")
        install(root, args.install)
        return
    work = args.work.resolve()
    if work == root or root in work.parents:
        parser.error("Build outside the game to keep generated sources out of Godot")
    if not work.exists():
        run("git", "clone", "--no-checkout", "https://github.com/rive-app/rive-wasm.git", str(work))
        run("git", "checkout", REVISION, cwd=work)
        run("git", "submodule", "init", cwd=work)
        run("git", "config", "submodule.wasm/submodules/rive-runtime.url",
            "https://github.com/rive-app/rive-runtime.git", cwd=work)
        run("git", "submodule", "update", "--init", "--depth", "1", cwd=work)
        run("git", "apply", str(Path(__file__).with_name("web_runtime.patch")), cwd=work)
    else:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
        if revision != REVISION:
            raise RuntimeError("Existing build checkout has the wrong revision; use a new directory")
        run("git", "apply", "--reverse", "--check", str(Path(__file__).with_name("web_runtime.patch")), cwd=work)
    run("bash", "./build_wasm.sh", "-c", "release", cwd=work / "wasm",
        env=dict(os.environ, OUT_DIR="build/citybuilder"))
    destination = root / "web/addon/web/vendor"
    destination.mkdir(parents=True, exist_ok=True)
    for source, name in [
        (work / "wasm/build/citybuilder/canvas_advanced.mjs", "canvas_advanced.mjs"),
        (work / "wasm/build/citybuilder/canvas_advanced.wasm", "rive.wasm"),
        (work / "LICENSE", "LICENSE"),
    ]:
        shutil.copyfile(source, destination / name)
    receipt = {
        "source": "https://github.com/rive-app/rive-wasm", "revision": REVISION,
        "runtime_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
            cwd=work / "wasm/submodules/rive-runtime", text=True).strip(),
        "emscripten": "4.0.23", "renderer": "Canvas2D",
        "bindings": ["Artboard.layoutBounds", "StateMachineInstance.needsAdvance"],
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(destination.iterdir()) if p.name != "build.json"},
    }
    (destination / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Built web runtime in {destination}")
    if args.install:
        install(root, args.install)


if __name__ == "__main__":
    main()
