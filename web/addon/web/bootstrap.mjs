import Rive from "./vendor/canvas_advanced.mjs";
import { createBridge } from "./surface.mjs";

export async function initialize() {
  const runtime = await Rive({ locateFile: () => new URL("./vendor/rive.wasm", import.meta.url).href });
  const response = await fetch(new URL("./manifest.json", import.meta.url));
  if (!response.ok) throw new Error(`Rive manifest: HTTP ${response.status}`);
  const manifest = await response.json();
  const files = new Map();
  const failures = new Map();
  await Promise.all(manifest.map(async ({ path, url }) => {
    try {
      const response = await fetch(new URL(url, import.meta.url));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      // All shipped fonts/images are embedded. Never request assets from Rive's CDN.
      const file = await runtime.load(new Uint8Array(await response.arrayBuffer()), undefined, false);
      if (!file) throw new Error("Runtime rejected file");
      files.set(path, file);
    } catch (error) {
      failures.set(path, `${path}: ${error.message || error}`);
      console.error("Rive preload:", path, error);
    }
  }));
  window.CityRive = createBridge(runtime, files, failures);
  return window.CityRive;
}
