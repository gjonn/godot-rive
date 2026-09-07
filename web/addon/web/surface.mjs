// Rive owns animation/layout; Godot owns composition and input. No DOM listeners or RAF loop.
export function createBridge(runtime, files, failures = new Map()) {
  const surfaces = new Set();
  const bridge = {
    ready: true,
    lastError: "",
    createSurface(path, artboard, machine, initialJSON) {
      let surface;
      try {
        const file = files.get(path);
        if (!file) throw new Error(failures.get(path) || `Rive file not preloaded: ${path}`);
        surface = new Surface(runtime, file, () => surfaces.delete(surface));
        surface.load(artboard, machine, JSON.parse(initialJSON));
        surfaces.add(surface);
        bridge.lastError = "";
        return surface;
      } catch (error) {
        surface?.dispose();
        bridge.lastError = String(error.message || error);
        console.error("Rive surface:", bridge.lastError);
        return null;
      }
    },
    diagnostics() {
      return { surfaces: surfaces.size, files: files.size,
        failures: Object.fromEntries(failures),
        renderCount: [...surfaces].reduce((sum, surface) => sum + surface.renderCount, 0) };
    },
    dispose() {
      for (const surface of [...surfaces]) surface.dispose();
      for (const file of files.values()) file.unref();
      files.clear();
      bridge.ready = false;
    },
  };
  return bridge;
}

class Surface {
  constructor(runtime, file, onDispose) {
    this.runtime = runtime;
    this.file = file;
    this.onDispose = onDispose;
    this.error = "";
    this.renderCount = 0;
    this.dirty = true;
    this.advancing = true;
    this.width = 0;
    this.height = 0;
    this.properties = new Map();
  }

  load(artboardName, machineName, initial) {
    this.artboard = this.file.artboardByName(artboardName);
    if (!this.artboard) throw new Error(`Missing Rive artboard: ${artboardName}`);
    if (typeof this.artboard.layoutBounds !== "function") {
      throw new Error("Rive web binary is missing the layoutBounds binding");
    }
    const machine = this.artboard.stateMachineByName(machineName);
    if (!machine) throw new Error(`Missing Rive state machine: ${machineName}`);
    this.machine = new this.runtime.StateMachineInstance(machine, this.artboard);
    this.model = this.file.defaultArtboardViewModel(this.artboard)?.defaultInstance();
    if (!this.model) throw new Error("Rive artboard has no default view model");
    for (const [name, value] of Object.entries(initial)) {
      if (!this.setValue(typeof value, name, value)) {
        throw new Error(`Invalid initial view model property: ${name}`);
      }
    }
    this.machine.bindViewModelInstance(this.model);
    this.canvas = document.createElement("canvas");
    this.context = this.canvas.getContext("2d", { willReadFrequently: true });
    if (!this.context) throw new Error("Cannot allocate Rive Canvas2D surface");
    this.renderer = this.runtime.makeRenderer(this.canvas);
    if (!this.resize(Math.round(this.artboard.width), Math.round(this.artboard.height))) {
      throw new Error("Invalid Rive artboard size");
    }
  }

  resize(width, height) {
    if (![width, height].every(n => Number.isInteger(n) && n >= 1 && n <= 4096)) return false;
    if (width === this.width && height === this.height) return true;
    this.width = this.canvas.width = this.artboard.width = width;
    this.height = this.canvas.height = this.artboard.height = height;
    this.pixelData = null;
    this.dirty = true;
    return true;
  }

  advance(seconds) {
    if (!this.machine || this.error || !Number.isFinite(seconds) || seconds < 0) return false;
    if (!this.dirty && !this.advancing && !this.machine.needsAdvance()) return false;
    try {
      this.advancing = this.machine.advanceAndApply(Math.min(seconds, 0.1));
      this.renderer.clear();
      this.renderer.save();
      this.artboard.draw(this.renderer);
      this.renderer.restore();
      // Canvas2D queues draw commands; flush before reading straight-alpha RGBA.
      this.runtime.resolveAnimationFrame();
      this.pixelData = this.context.getImageData(0, 0, this.width, this.height).data;
      this.dirty = false;
      this.renderCount++;
      return true;
    } catch (error) {
      this.error = String(error.message || error);
      console.error("Rive render:", this.error);
      return false;
    }
  }

  pixels() { return this.pixelData; }

  property(type, name) {
    if (!this.model || !["boolean", "string", "number"].includes(type)) return null;
    const key = `${type}:${name}`;
    if (!this.properties.has(key)) this.properties.set(key, this.model[type](name));
    return this.properties.get(key);
  }

  setValue(type, name, value) {
    if (typeof value !== type) return false;
    if (type === "number") {
      if (!Number.isFinite(value) || Math.abs(value) > 3.4028234663852886e38) return false;
      value = Math.fround(value);
    }
    const property = this.property(type, name);
    if (!property) return false;
    if (property.value !== value) {
      property.value = value;
      this.dirty = true;
    }
    return true;
  }

  getValue(type, name, fallback) { return this.property(type, name)?.value ?? fallback; }

  layoutRect(name) { return JSON.stringify(this.artboard?.layoutBounds(name) ?? null); }

  pointer(method, x, y) {
    if (!this.machine || ![x, y].every(Number.isFinite)) return;
    if (!["pointerMove", "pointerDown", "pointerUp"].includes(method)) return;
    this.machine[method](x, y);
    this.dirty = true;
  }

  dispose() {
    this.machine?.delete();
    this.machine = null;
    // Property wrappers are owned by the VM. Release them before the VM and artboard.
    this.properties.clear();
    this.model?.unref();
    this.model = null;
    this.artboard?.delete();
    this.artboard = null;
    this.renderer?.delete();
    this.renderer = null;
    if (this.canvas) this.canvas.width = this.canvas.height = 0;
    this.canvas = this.context = this.pixelData = null;
    this.onDispose();
  }
}
