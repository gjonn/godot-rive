# Rive web backend for Godot 4.7

This backend renders the official Rive Canvas2D runtime into ordinary Godot
ImageTextures. It uses the same surface methods as the Apple CoreGraphics backend,
so Controls retain input, focus, clipping, draw order and accessibility. It does
not require a web GDExtension or a custom Godot engine template.

## Install

From this repository, install the bundled, checksummed browser runtime:

```sh
python3 build/build_web.py --install /path/to/game/addons/rive
```

The installer preserves existing macOS/iOS libraries and their descriptor. Install
at `res://addons/rive`; the adapter and plugin paths currently assume that location.
Enable **Rive Web Export** in **Project Settings → Plugins**.

In **Project → Export → Web**:

1. Resources → non-resource include filter: add `assets/ui/rive/*.riv`.
2. Resources → exclude filter: add `addons/rive/rive_surface.gdextension`.
3. Options → HTML → Custom HTML Shell: select `res://addons/rive/web/shell.html`.
4. Leave Extensions Support and Thread Support disabled for this backend.

Preserve any other filter entries. The exclusion in step 2 is necessary even when
Extensions Support is disabled: otherwise Godot tries to load the Apple-only
extension and reports that no `wasm32` library exists.

The export plugin copies `.riv` files directly from `res://assets/ui/rive/`, plus
the browser runtime and its license, into a `rive/` folder beside the exported
HTML. Keep that entire folder alongside Godot's HTML, JS, WASM and PCK files when
hosting. Serve via HTTP(S), not a `file://` URL. If your project keeps artwork in
another directory, update `ART_ROOT` in `web_export.gd` and the include filter.
The supplied shell is based on Godot 4.7.2's standard shell; custom shells must
await `import('./rive/bootstrap.mjs').then(module => module.initialize())` before
calling `engine.startGame(...)`.

Replace platform-specific construction in your host with:

```gdscript
var surface: RefCounted
if RiveRuntime.is_available():
    surface = RiveRuntime.create_surface()
    if not surface.call("load_file", "res://assets/ui/rive/example.riv",
            "Main", "Main", {"reducedMotion": true}):
        push_warning(surface.call("get_error"))
        surface = null
```

The shared factory selects the native `RiveSurface` on Apple targets and the
GDScript/JavaScript adapter on Web. Existing native fallback controls remain the
host's responsibility when loading fails. See [the surface API](../native/README.md#api).

## Runtime and ownership

- The shell initializes WASM and preloads the manifest before Godot starts. Files
  share imported assets, but each surface has its own artboard, state machine and
  default view-model instance. Files that fail to load report their own errors.
- Initial boolean, string and finite number values apply before the first advance.
  Sizes are limited to 1–4096 pixels per axis; each advance caps time at 0.1 seconds.
- No DOM input listeners or independent animation loop are installed. The host
  decides when visible surfaces advance. Settled surfaces retain their texture
  without rendering or copying pixels again.
- Canvas2D readback supplies straight-alpha RGBA. Animated frames copy pixels into
  Godot and upload a texture; large animated surfaces therefore have a cost that
  should be measured on target devices.
- `get_layout_rect()` uses the real named Rive LayoutComponent bounds. Keep
  **Export name** enabled on layout components used for native hit targets.
- Godot's RefCounted teardown releases the JS surface, state machine, view model,
  artboard, renderer and pixels. Cached files live for the page lifetime. The
  bootstrap exposes `window.CityRive.diagnostics()` for counts and preload errors.
- This build enables text and layout, and disables audio, scripting and SIMD. It
  uses Canvas2D rather than the Rive GPU renderer. Browser graphics support is
  separate from the native backend's feature limits.

## Rebuild

```sh
python3 build/build_web.py --work /tmp/rive-web-build \
  --install /path/to/game/addons/rive
```

Use a new, dedicated directory, or reuse one created by this script. The build
pins the official `rive-app/rive-wasm` revision and its runtime submodule. Upstream
provisions Emscripten 4.0.23 and build dependencies. The local
[`web_runtime.patch`](../build/web_runtime.patch) exposes only two additional host
methods, `Artboard.layoutBounds` and `StateMachineInstance.needsAdvance`, and
selects the text/layout build without Java-based JS minification. The generated
module and WASM must always be installed together. Their source revisions and
SHA-256 checksums are recorded in `addon/web/vendor/build.json`.

## Verification

The initial integration was tested with Godot 4.7.2 and Chromium: actual exported
main-menu → city navigation, Build open/close, keyboard focus, screenshots at
1152×648 and 640×480, and 263 assertions spanning 13 CityBuilder artboards. Checks
cover resizing, named slots, visible/transparent pixels, bindings, independent
instances, invalid values, idle rendering and teardown. The existing macOS menu
also reported its native Rive surface loaded after the factory change.

The browser probe deliberately uses the companion CityBuilder artwork and interaction
layout; those assets remain in the game repository, as with the native probe.
Against a served CityBuilder Web export, with Playwright/Chromium installed:

```sh
WEB_URL=http://127.0.0.1:8768/export/web/index.html \
  node web/tests/browser_probe.mjs
```

Set `PLAYWRIGHT_MODULE` to an absolute `playwright/index.mjs` path if installed
elsewhere; `QA_OUTPUT` chooses the screenshot and assertion output directory.
Safari, Firefox, mobile-browser performance, custom hosting policies and the full
HUD interaction matrix have not been verified. This is not a claim that every
Rive feature or browser is supported.
