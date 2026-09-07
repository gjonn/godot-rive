@tool
extends EditorExportPlugin

const WEB_ROOT := "res://addons/rive/web/"
const ART_ROOT := "res://assets/ui/rive/"
const WEB_FILES: Array[String] = ["bootstrap.mjs", "surface.mjs",
	"vendor/canvas_advanced.mjs", "vendor/rive.wasm", "vendor/LICENSE",
	"licenses/rive_surface.txt", "licenses/rive_runtime.txt", "licenses/godot.txt",
	"licenses/harfbuzz.txt", "licenses/sheenbidi.txt", "licenses/yoga.txt"]


func _get_name() -> String:
	return "RiveWebExport"


func _export_begin(features: PackedStringArray, _debug: bool, path: String, _flags: int) -> void:
	if not features.has("web") or path.get_extension() == "pck":
		return
	var target := path.get_base_dir().path_join("rive")
	for file in WEB_FILES:
		if not _copy(WEB_ROOT.path_join(file), target.path_join(file)):
			return
	var manifest: Array[Dictionary] = []
	for file in DirAccess.get_files_at(ART_ROOT):
		if file.get_extension() != "riv":
			continue
		if not _copy(ART_ROOT.path_join(file), target.path_join("assets/" + file)):
			return
		manifest.append({"path": ART_ROOT.path_join(file), "url": "assets/" + file})
	var output := FileAccess.open(target.path_join("manifest.json"), FileAccess.WRITE)
	if output == null:
		_fail("Cannot write the Rive web manifest")
		return
	output.store_string(JSON.stringify(manifest, "\t"))


func _copy(source: String, target: String) -> bool:
	var error := DirAccess.make_dir_recursive_absolute(target.get_base_dir())
	if error == OK:
		error = DirAccess.copy_absolute(source, target)
	if error != OK:
		_fail("Cannot bundle %s: %s" % [source, error_string(error)])
	return error == OK


func _fail(message: String) -> void:
	get_export_platform().add_message(EditorExportPlatform.EXPORT_MESSAGE_ERROR,
		"Rive web runtime", message)
