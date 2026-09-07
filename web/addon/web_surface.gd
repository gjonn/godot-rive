extends RefCounted

## Rive Canvas2D pixels stay inside Godot's canvas: clipping, modulation and input are native.
## The JavaScript handle owns WASM objects and must be explicitly released on PREDELETE.
var _handle: JavaScriptObject
var _image: Image
var _texture: ImageTexture
var _size := Vector2i.ZERO
var _error := ""
var _render_ms := 0.0


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		clear()


func load_file(path: String, artboard: String, machine: String, initial: Dictionary) -> bool:
	clear()
	var bridge := JavaScriptBridge.get_interface("CityRive")
	if bridge == null or not bool(bridge.ready):
		_error = "Rive web runtime was not initialized by the export shell"
		return false
	_handle = bridge.createSurface(path, artboard, machine, JSON.stringify(initial))
	if _handle == null:
		_error = str(bridge.lastError)
		return false
	_size = Vector2i(int(_handle.width), int(_handle.height))
	return true


func clear() -> void:
	if _handle != null:
		_handle.dispose()
	_handle = null
	_texture = null
	_image = null
	_size = Vector2i.ZERO
	_error = ""
	_render_ms = 0.0


func is_loaded() -> bool:
	return _handle != null and str(_handle.error).is_empty()


func get_error() -> String:
	return str(_handle.error) if _handle != null else _error


func resize(value: Vector2i) -> bool:
	if not is_loaded() or not bool(_handle.resize(value.x, value.y)):
		return false
	if value != _size:
		_size = value
		_image = null
		_texture = null
	return true


func get_size() -> Vector2i:
	return _size


func advance(seconds: float) -> bool:
	if not is_loaded():
		return false
	var started := Time.get_ticks_usec()
	if not bool(_handle.advance(seconds)):
		return false
	var buffer: JavaScriptObject = _handle.pixels()
	var pixels := JavaScriptBridge.js_buffer_to_packed_byte_array(buffer)
	if pixels.size() != _size.x * _size.y * 4:
		_error = "Rive web renderer returned an invalid RGBA buffer"
		return false
	_image = Image.create_from_data(_size.x, _size.y, false, Image.FORMAT_RGBA8, pixels)
	if _texture == null:
		_texture = ImageTexture.create_from_image(_image)
	else:
		_texture.update(_image)
	_render_ms = float(Time.get_ticks_usec() - started) / 1000.0
	return true


func get_texture() -> ImageTexture:
	return _texture


func get_image() -> Image:
	return _image


func set_boolean(property: String, value: bool) -> bool:
	return is_loaded() and bool(_handle.setValue("boolean", property, value))


func get_boolean(property: String) -> bool:
	return is_loaded() and bool(_handle.getValue("boolean", property, false))


func set_text(property: String, value: String) -> bool:
	return is_loaded() and bool(_handle.setValue("string", property, value))


func get_text(property: String) -> String:
	return str(_handle.getValue("string", property, "")) if is_loaded() else ""


func set_number(property: String, value: float) -> bool:
	return is_loaded() and bool(_handle.setValue("number", property, value))


func get_number(property: String) -> float:
	return float(_handle.getValue("number", property, 0.0)) if is_loaded() else 0.0


func get_layout_rect(slot: String) -> Rect2:
	if not is_loaded():
		return Rect2()
	var bounds: Variant = JSON.parse_string(str(_handle.layoutRect(slot)))
	if not bounds is Array or bounds.size() != 4:
		return Rect2()
	return Rect2(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))


func pointer_move(position: Vector2) -> void:
	if is_loaded():
		_handle.pointer("pointerMove", position.x, position.y)


func pointer_down(position: Vector2) -> void:
	if is_loaded():
		_handle.pointer("pointerDown", position.x, position.y)


func pointer_up(position: Vector2) -> void:
	if is_loaded():
		_handle.pointer("pointerUp", position.x, position.y)


func get_render_count() -> int:
	return int(_handle.renderCount) if _handle != null else 0


func get_last_render_ms() -> float:
	return _render_ms
