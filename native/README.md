# RiveSurface for Godot 4.7

Maintained source: https://github.com/gjonn/godot-rive

This backend loads current `.riv` files using the pinned official Rive C++
runtime. It supports the menu's layout, embedded text, gradients, trim paths,
state machines and boolean/string view-model bindings. It renders transparent
RGBA through Rive's CoreGraphics renderer into a cached Godot ImageTexture.

The included build targets **macOS arm64**, tested on Godot 4.7.2 / Mobile.
Windows, Linux, Android, iOS and web binaries are not provided. This is not a
claim that every Rive feature is supported: scripting, audio and the Rive GPU
renderer are disabled. The CoreGraphics backend does not implement image meshes.

## API

Create `RiveSurface` (a RefCounted) and call
`load_file(path, artboard_name, state_machine_name, initial_values)`.
The artboard needs a default view-model instance. Boolean/string initial values
are applied before the first state-machine advance, including reduced motion.
`is_loaded()` and `get_error()` report failure without substituting artwork.

- `resize(Vector2i)` changes the artboard's actual layout size (1–4096 per axis).
- `advance(seconds)` advances and uploads a frame only when dirty or animating;
  returns whether the texture changed. Each call caps its time step at 0.1 s.
- `get_texture()` gives the current ImageTexture. Re-read after resize because
  resizing replaces the texture. `get_image()` exposes the straight-alpha pixels.
- `set_boolean` / `get_boolean`, `set_text` / `get_text` address VM properties by
  name. Setters return false for unknown properties or incompatible types.
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
