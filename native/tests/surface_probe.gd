extends SceneTree

## Usage: godot --headless --script surface_probe.gd -- extension.gdextension menu.riv
## The companion menu fixture stays in its game repository, not in the plugin.

var _failures := 0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		printerr("Expected extension.gdextension and menu.riv paths")
		quit(2)
		return
	GDExtensionManager.load_extension(args[0])
	if not ClassDB.class_exists(&"RiveSurface"):
		printerr("RiveSurface was not registered")
		quit(1)
		return
	var surface: RefCounted = ClassDB.instantiate(&"RiveSurface")
	_check(bool(surface.call("load_file", args[1], "MainMenu", "MainMenu", {})),
		"current export loads")
	if not bool(surface.call("is_loaded")):
		printerr(surface.call("get_error"))
		quit(1)
		return
	_advance(surface, 120)
	_check(surface.call("get_layout_rect", "Play_Slot") == Rect2(424, 360, 304, 72),
		"reference hit rectangle comes from the exported layout")
	var image: Image = surface.call("get_image")
	_check(image.get_size() == Vector2i(1152, 648), "reference texture size")
	_check(image.get_pixel(0, 0).a == 0.0, "background remains transparent")
	_check(image.get_pixel(450, 390).a > 0.95, "button is visible")
	var idle_count: int = surface.call("get_render_count")
	_advance(surface, 120)
	_check(int(surface.call("get_render_count")) == idle_count, "idle skips rendering")
	surface.call("resize", Vector2i(640, 360))
	surface.call("advance", 0.0)
	_check(surface.call("get_layout_rect", "Play_Slot") == Rect2(168, 216, 304, 72),
		"compact layout keeps the touch target")
	surface.call("pointer_move", Vector2(320, 252))
	_advance(surface, 12)
	_check(bool(surface.call("get_boolean", "hovered")), "Rive pointer hover listener")
	surface.call("pointer_down", Vector2(320, 252))
	_advance(surface, 12)
	_check(bool(surface.call("get_boolean", "pressed")), "Rive pointer down listener")
	surface.call("pointer_up", Vector2(320, 252))
	_advance(surface, 12)
	_check(bool(surface.call("get_boolean", "playRequested")), "Rive click request")
	_check(bool(surface.call("get_boolean", "loading")), "Rive click enters loading")
	_check(surface.call("get_text", "status") == "Preparing your city…", "bound loading text")
	surface.call("set_boolean", "reducedMotion", true)
	_advance(surface, 120)
	var reduced_count: int = surface.call("get_render_count")
	_advance(surface, 120)
	_check(int(surface.call("get_render_count")) == reduced_count, "reduced loading is static")
	surface.call("set_boolean", "loading", false)
	surface.call("set_boolean", "playRequested", false)
	surface.call("set_text", "status", "Try again")
	_advance(surface, 30)
	_check(not bool(surface.call("get_boolean", "loading")), "loading can recover")
	_check(surface.call("get_text", "status") == "Try again", "host updates text")
	_check(not bool(surface.call("set_boolean", "missing", true)), "unknown binding rejected")
	_check(not bool(surface.call("resize", Vector2i.ZERO)), "invalid surface size rejected")
	surface.call("clear")
	_check(not bool(surface.call("is_loaded")), "clear releases the runtime")
	_check(bool(surface.call("load_file", args[1], "MainMenu", "MainMenu",
		{"reducedMotion": true})), "reload creates an independent instance")
	_advance(surface, 20)
	_check(not bool(surface.call("get_boolean", "loading")), "reload restores defaults")
	surface.call("clear")
	surface = null
	print("SURFACE_PROBE_FAILURES=", _failures)
	quit(0 if _failures == 0 else 1)


func _advance(surface: RefCounted, frames: int) -> void:
	for frame in frames:
		surface.call("advance", 1.0 / 60.0)


func _check(condition: bool, label: String) -> void:
	if condition:
		print("PASS ", label)
	else:
		_failures += 1
		printerr("FAIL ", label)
