# Godot Rive

A maintained Rive integration for Godot 4.7, based on the original
[kibble-cabal/godot-rive](https://github.com/kibble-cabal/godot-rive) source history.
This is an independent repository.

The current `RiveSurface` backend loads modern Rive exports with layout, embedded
text, state machines and boolean/string view-model bindings. It renders a
transparent texture through CoreGraphics and skips redraws once animation settles.
The host keeps native Godot input, focus and accessibility controls.

## Current support

- Tested: Godot **4.7.2**, **macOS arm64**, Mobile renderer.
- Includes debug/release build targets and a regression probe.
- iOS arm64 device debug/release XCFrameworks compile and link with Xcode 26.6;
  exported-game rendering and performance have not yet been tested on a device.
- Windows x86_64 builds use the Rive D3D11 renderer and a static C++ runtime.
- Linux, Android, web, Intel macOS and iOS simulator binaries are not included.
- Rive scripting and audio are disabled. The Apple CoreGraphics backend does not support image meshes.

See [the backend documentation](native/README.md) for the API, limits and checks.

## Download and install

Download **rive-addon-all-platforms.zip** from [Releases](https://github.com/gjonn/godot-rive/releases).
Extract it into your Godot project root so the descriptor is at
`addons/rive/rive_surface.gdextension`, then restart Godot. No compiler is needed.
Godot selects the correct library automatically; this is a GDExtension, so there
is no editor plugin checkbox to enable.

The single ZIP includes debug and release libraries for **macOS Apple Silicon
(arm64)**, **iOS arm64 devices (15+)**, and **Windows x86_64**, plus licenses and
a source revision/file hash manifest. iOS uses static XCFrameworks; building,
signing and installing your game on an iPhone still requires Xcode. Include
your `.riv` files in Godot's non-resource export filter.

For a development build, open a successful **Build addon** run under
[Actions](https://github.com/gjonn/godot-rive/actions/workflows/build-addon.yml)
and download **rive-addon-all-platforms.zip**. These downloads require a GitHub
login and expire after 30 days. The `internal-*` artifacts are temporary build
inputs, not addon downloads.

## Continuous builds and releases

The workflow builds all three platforms on native hosted runners on relevant
pull requests, main-branch pushes, `v*` tag pushes, or **Run workflow**. Each build
installs both targets and checks its files; desktop jobs load the library and
check its entry point, and iOS builds link-check every packaged device archive.
Packaging waits for every platform, verifies the complete library inventory and
licenses, rebuilds the combined descriptor, and checks the final ZIP. These are
build/load checks; they do not verify game rendering or iPhone deployment.

To release, push a version tag such as `v0.2.0`. After all jobs pass, the workflow
creates a **draft GitHub release** and attaches the single all-platform ZIP.
Review and publish the draft to make it available in Releases. Reruns can replace
the asset on a draft, but refuse to modify an already published release. No
signing certificates or custom repository secrets are required.

## Build from source

Clone with submodules, then run on Apple Silicon with Xcode Command Line Tools:

```sh
git submodule update --init --recursive
python3 -m venv .build-venv
.build-venv/bin/pip install -r build/requirements.txt
.build-venv/bin/python build/build.py --install /path/to/game/addons/rive
```

Both native libraries, the extension descriptor and license notices are copied
into the target addon directory. Restart Godot when replacing a loaded library.
Dependency versions are pinned by gitlinks and Rive's dependency build scripts.

With full Xcode installed, build and install iOS device packages alongside macOS:

```sh
.build-venv/bin/python build/build.py --platform ios --install /path/to/game/addons/rive
```

Include your `.riv` assets in Godot's non-resource export filter. See
[iOS packaging details](native/README.md#build-and-install).

On Windows x64, install Python 3.12, Visual Studio 2022 C++ Build Tools and a
Windows SDK (including `fxc`), initialize the submodules, then run:

```powershell
python -m pip install -r build/requirements.txt
python build/build.py --platform windows --install C:/path/to/game/addons/rive
```

The builder finds the MSVC developer environment, downloads pinned Premake,
compiles shaders, and builds the Rive runtime and both wrapper DLLs.

## Source history

The upstream `src/`, `demo/`, screenshots and legacy Skia build files remain for
reference. Their viewer API and bundled binaries are not the current backend and
should not be installed alongside `RiveSurface`. New backend code lives under
`native/` with its own MIT license; third-party licenses remain with their sources.
