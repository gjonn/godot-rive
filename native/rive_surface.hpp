#pragma once

#include <godot_cpp/classes/ref_counted.hpp>
#include <godot_cpp/classes/image.hpp>
#include <godot_cpp/classes/image_texture.hpp>
#include <godot_cpp/variant/dictionary.hpp>
#include <godot_cpp/variant/rect2.hpp>
#include <godot_cpp/variant/vector2i.hpp>
#include <memory>

namespace godot {

// Owns one file/artboard/state machine/VM and a cached transparent texture.
// Input/focus remain with native Godot Controls; no engine event is intercepted.
class RiveSurface : public RefCounted {
    GDCLASS(RiveSurface, RefCounted)
    struct Impl;
    std::unique_ptr<Impl> impl;

protected:
    static void _bind_methods();

public:
    RiveSurface();
    ~RiveSurface();
    bool load_file(const String &path, const String &artboard_name,
                   const String &state_machine_name, const Dictionary &initial_values);
    void clear();
    bool is_loaded() const;
    String get_error() const;
    bool resize(Vector2i size);
    Vector2i get_size() const;
    bool advance(double seconds);
    Ref<ImageTexture> get_texture() const;
    Ref<Image> get_image() const;
    bool set_boolean(const String &name, bool value);
    bool get_boolean(const String &name) const;
    bool set_text(const String &name, const String &value);
    String get_text(const String &name) const;
    Rect2 get_layout_rect(const String &name) const;
    void pointer_move(Vector2 position);
    void pointer_down(Vector2 position);
    void pointer_up(Vector2 position);
    int64_t get_render_count() const;
    double get_last_render_ms() const;
};
}
