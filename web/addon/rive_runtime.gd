class_name RiveRuntime
extends RefCounted

## Shared synchronous surface contract. The web shell finishes loading Rive before Godot starts.
const WebSurface := preload("res://addons/rive/web_surface.gd")


static func is_available() -> bool:
	if OS.has_feature("web"):
		var bridge := JavaScriptBridge.get_interface("CityRive")
		return bridge != null and bool(bridge.ready)
	return ClassDB.class_exists(&"RiveSurface")


static func create_surface() -> RefCounted:
	if not is_available():
		return null
	if OS.has_feature("web"):
		return WebSurface.new()
	return ClassDB.instantiate(&"RiveSurface") as RefCounted
