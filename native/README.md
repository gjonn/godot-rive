# RiveSurface for Godot 4.7

Maintained source: https://github.com/gjonn/godot-rive

This backend loads current `.riv` files using the pinned official Rive C++
runtime. It supports the menu's layout, embedded text, gradients, trim paths,
state machines and boolean/string/number view-model bindings. It renders transparent
RGBA through Rive's CoreGraphics renderer into a cached Godot ImageTexture.

The build targets **macOS arm64**, **iOS arm64 devices** (iOS 15+ by default),
and **Windows x86_64**. Windows uses Rive's D3D11 renderer with texture readback.
macOS runtime behavior is tested on Godot 4.7.2 / Mobile. iOS debug/release
XCFrameworks have passed native compilation and entry-point linking with Xcode
26.6; game export, device rendering and performance remain unverified.
Linux, Android and web binaries are not provided. Scripting and audio are
disabled. The Apple CoreGraphics backend does not implement image meshes.

Prebuilt downloads: [Releases](https://github.com/gjonn/godot-rive/releases).
Extract `rive-addon-all-platforms.zip` into your project root and restart Godot.
The addon directory includes every supported platform and both build targets;
Godot automatically selects the matching library. No editor plugin toggle is
needed. iOS game export still requires Xcode and signing; this bundle contains
device slices only, not simulator or Intel macOS binaries.

## API

Create `RiveSurface` (a RefCounted) and call
`load_file(path, artboard_name, state_machine_name, initial_values)`.
The artboard needs a default view-model instance. Boolean/string/number initial values
are applied before the first state-machine advance, including reduced motion.
`is_loaded()` and `get_error()` report failure without substituting artwork.

- `resize(Vector2i)` changes the artboard's actual layout size (1–4096 per axis).
- `advance(seconds)` advances and uploads a frame only when dirty or animating;
  returns whether the texture changed. Each call caps its time step at 0.1 s.
- `get_texture()` gives the current ImageTexture. Re-read after resize because
  resizing replaces the texture. `get_image()` exposes the straight-alpha pixels.
- `set_boolean` / `get_boolean`, `set_text` / `get_text` address VM properties by
  name. Setters return false for unknown properties or incompatible types.
- `set_number` / `get_number` address numeric VM properties using Rive's float
  precision. Setters reject non-finite and out-of-range values. Unknown reads
  return zero; validate property names through setters. Unchanged values do
  not dirty the rendering surface.
- `get_layout_rect(name)` reports a LayoutComponent's artboard-space rectangle.
  Enable **Export name** on that component in Rive; stripped names cannot resolve.
- `pointer_move`, `pointer_down`, `pointer_up` accept artboard coordinates for
  hosts that route pointer events directly to Rive.
- `get_render_count()` and `get_last_render_ms()` expose rendering diagnostics.
- `clear()` releases the state machine, VM, artboard, file and rendering surface.

Use a native Godot Control for focus, touch/controller handling and accessibility.
Do not send the same activation through both the native control and Rive's pointer
listeners. The game owns loading, recovery, transitions and input consumption.
Straight-alpha conversion avoids dark fringes over the game. No Rive processing
or GPU upload is needed once a state settles; the texture remains available.

## Build and install

From a recursive checkout on Apple Silicon with Xcode Command Line Tools:

```sh
python3 -m venv .build-venv
.build-venv/bin/pip install -r build/requirements.txt
.build-venv/bin/python build/build.py --install /path/to/game/addons/rive
```

The build script fails on any build or dependency error. Both debug and release
libraries are installed with the descriptor and third-party license notices.
Restart Godot after replacing a loaded native library; hot reload is disabled.

For iOS, install full Xcode with the iPhone SDK, then run:

```sh
.build-venv/bin/python build/build.py --platform ios --install /path/to/game/addons/rive
```

This builds Rive (text/layout enabled), its CoreGraphics renderer, HarfBuzz,
SheenBidi, Yoga, godot-cpp and RiveSurface for the iPhone SDK. It merges each
target's static dependencies into one XCFramework, preserving the existing
macOS binaries and descriptor entries. Clang module autolinking carries the
CoreGraphics, CoreFoundation, CoreText and ImageIO dependencies into Xcode;
no manual framework additions are needed. Each package must pass a standalone
iOS executable link that references `rive_surface_init` before it is installed.
That check does not export, sign or run the game.

The installed packages contain an `ios-arm64` device slice. `--simulator` can
add a separately built arm64 simulator slice; that optional path has not been
validated in the initial device build. `--ios-min-version` defaults to 15.0
for the wrapper and link probe; the pinned Rive libraries target iOS 13.0.

In Godot's iOS export preset, include `assets/ui/rive/*.riv` (or the equivalent
path for your project) in the non-resource export filter. RiveSurface reads
these files directly through FileAccess, so Export All Resources alone is not
sufficient. The installed `.gdextension` selects the debug/release iOS package.

The source pins are the repository's `godot-cpp` and `thirdparty/rive-cpp`
gitlinks. Rive's own build scripts pin its HarfBuzz, SheenBidi and Yoga dependencies.
The new code under `native/` has its own MIT license. The old `src/`, demo and
Skia build files remain as historical upstream material and are not linked here.

## Regression probe

Given the companion CityBuilder `MainMenu` export (kept with the game):

```sh
/Applications/Godot.app/Contents/MacOS/Godot --headless --path build/native \
  --script "$PWD/native/tests/surface_probe.gd" -- \
  /absolute/path/to/build/native/rive_surface.gdextension \
  /absolute/path/to/citybuilder_main_menu.riv
```

The probe checks current-file import, layout resizing, visible/transparent pixels,
pointer listeners and start request, text binding, reduced motion, recovery,
invalid arguments, teardown/reload, and no redraws after states settle.
