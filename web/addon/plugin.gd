@tool
extends EditorPlugin

const WebExport := preload("res://addons/rive/web_export.gd")
var _export_plugin: EditorExportPlugin


func _enter_tree() -> void:
	_export_plugin = WebExport.new()
	add_export_plugin(_export_plugin)


func _exit_tree() -> void:
	remove_export_plugin(_export_plugin)
	_export_plugin = null
