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
- Windows, Linux, Android, iOS and web binaries are not provided.
- Rive scripting, audio, GPU rendering and image meshes are not supported here.

See [the backend documentation](native/README.md) for the API, limits and checks.

## Build and install

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

## Source history

The upstream `src/`, `demo/`, screenshots and legacy Skia build files remain for
reference. Their viewer API and bundled binaries are not the current backend and
should not be installed alongside `RiveSurface`. New backend code lives under
`native/` with its own MIT license; third-party licenses remain with their sources.
