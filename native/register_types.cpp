#include "rive_surface.hpp"
#include <godot_cpp/godot.hpp>

using namespace godot;

static void initialize_rive(ModuleInitializationLevel level) {
    if (level == MODULE_INITIALIZATION_LEVEL_SCENE) GDREGISTER_CLASS(RiveSurface);
}
static void uninitialize_rive(ModuleInitializationLevel) {}

extern "C" {
GDExtensionBool GDE_EXPORT rive_surface_init(GDExtensionInterfaceGetProcAddress get_proc_address,
        GDExtensionClassLibraryPtr library, GDExtensionInitialization *initialization) {
    GDExtensionBinding::InitObject init(get_proc_address, library, initialization);
    init.register_initializer(initialize_rive);
    init.register_terminator(uninitialize_rive);
    init.set_minimum_library_initialization_level(MODULE_INITIALIZATION_LEVEL_SCENE);
    return init.init();
}
}
