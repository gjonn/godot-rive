#include "rive_surface.hpp"
#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/variant/utility_functions.hpp>
#include <rive/file.hpp>
#include <rive/artboard.hpp>
#include <rive/layout_component.hpp>
#include <rive/animation/state_machine_instance.hpp>
#include <rive/viewmodel/runtime/viewmodel_instance_runtime.hpp>
#ifdef _WIN32
#include "d3d_surface.hpp"
#else
#include <cg_factory.hpp>
#include <cg_renderer.hpp>
#endif
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <limits>
#include <vector>

using namespace godot;

struct RiveSurface::Impl {
    // Factory outlives all Rive objects; machine is released before its artboard.
#ifdef _WIN32
    D3DSurface backend;
#else
    rive::CGFactory factory;
    CGContextRef context = nullptr;
#endif
    rive::rcp<rive::File> file;
    std::unique_ptr<rive::ArtboardInstance> artboard;
    rive::rcp<rive::ViewModelInstanceRuntime> model;
    std::unique_ptr<rive::StateMachineInstance> machine;
    std::vector<uint8_t> pixels;
    PackedByteArray straight_pixels;
    Ref<Image> image;
    Ref<ImageTexture> texture;
    Vector2i size;
    String error;
    bool dirty = true;
    bool advancing = true;
    int64_t render_count = 0;
    double render_ms = 0.0;

    ~Impl() {
        machine.reset();
        model = nullptr;
        artboard.reset();
        file = nullptr;
#ifndef _WIN32
        if (context) CGContextRelease(context);
#endif
    }

    bool render() {
        if (!artboard) return false;
        const auto started = std::chrono::steady_clock::now();
#ifdef _WIN32
        if (!backend.render(artboard.get(), pixels)) {
            error = String::utf8(backend.error().c_str());
            return false;
        }
#else
        if (!context) return false;
        std::fill(pixels.begin(), pixels.end(), 0);
        {
            rive::CGRenderer renderer(context, size.x, size.y);
            artboard->draw(&renderer);
        }
#endif
        // Both backends write premultiplied RGBA. Godot's ordinary canvas blend
        // expects straight alpha; undo it once, avoiding dark vector-edge halos.
        uint8_t *dst = straight_pixels.ptrw();
        for (size_t p = 0; p < pixels.size(); p += 4) {
            const unsigned a = pixels[p + 3];
            dst[p + 3] = static_cast<uint8_t>(a);
            for (size_t c = 0; c < 3; ++c) {
                dst[p + c] = a ? static_cast<uint8_t>(
                    std::min(255u, (pixels[p + c] * 255u + a / 2u) / a)) : 0;
            }
        }
        if (image.is_null()) {
            image = Image::create_from_data(size.x, size.y, false,
                                           Image::FORMAT_RGBA8, straight_pixels);
        } else {
            image->set_data(size.x, size.y, false, Image::FORMAT_RGBA8, straight_pixels);
        }
        if (texture.is_null()) texture = ImageTexture::create_from_image(image);
        else texture->update(image);
        ++render_count;
        render_ms = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - started).count();
        return true;
    }
};

RiveSurface::RiveSurface() : impl(std::make_unique<Impl>()) {}
RiveSurface::~RiveSurface() = default;

void RiveSurface::_bind_methods() {
    ClassDB::bind_method(D_METHOD("load_file", "path", "artboard_name", "state_machine_name",
                                 "initial_values"), &RiveSurface::load_file);
    ClassDB::bind_method(D_METHOD("clear"), &RiveSurface::clear);
    ClassDB::bind_method(D_METHOD("is_loaded"), &RiveSurface::is_loaded);
    ClassDB::bind_method(D_METHOD("get_error"), &RiveSurface::get_error);
    ClassDB::bind_method(D_METHOD("resize", "size"), &RiveSurface::resize);
    ClassDB::bind_method(D_METHOD("get_size"), &RiveSurface::get_size);
    ClassDB::bind_method(D_METHOD("advance", "seconds"), &RiveSurface::advance);
    ClassDB::bind_method(D_METHOD("get_texture"), &RiveSurface::get_texture);
    ClassDB::bind_method(D_METHOD("get_image"), &RiveSurface::get_image);
    ClassDB::bind_method(D_METHOD("set_boolean", "name", "value"), &RiveSurface::set_boolean);
    ClassDB::bind_method(D_METHOD("get_boolean", "name"), &RiveSurface::get_boolean);
    ClassDB::bind_method(D_METHOD("set_text", "name", "value"), &RiveSurface::set_text);
    ClassDB::bind_method(D_METHOD("get_text", "name"), &RiveSurface::get_text);
    ClassDB::bind_method(D_METHOD("set_number", "name", "value"), &RiveSurface::set_number);
    ClassDB::bind_method(D_METHOD("get_number", "name"), &RiveSurface::get_number);
    ClassDB::bind_method(D_METHOD("get_layout_rect", "name"), &RiveSurface::get_layout_rect);
    ClassDB::bind_method(D_METHOD("pointer_move", "position"), &RiveSurface::pointer_move);
    ClassDB::bind_method(D_METHOD("pointer_down", "position"), &RiveSurface::pointer_down);
    ClassDB::bind_method(D_METHOD("pointer_up", "position"), &RiveSurface::pointer_up);
    ClassDB::bind_method(D_METHOD("get_render_count"), &RiveSurface::get_render_count);
    ClassDB::bind_method(D_METHOD("get_last_render_ms"), &RiveSurface::get_last_render_ms);
}

void RiveSurface::clear() { impl = std::make_unique<Impl>(); }
bool RiveSurface::is_loaded() const { return impl->machine != nullptr; }
String RiveSurface::get_error() const { return impl->error; }

bool RiveSurface::load_file(const String &path, const String &artboard_name,
                            const String &state_machine_name, const Dictionary &initial_values) {
    clear();
    const auto bytes = FileAccess::get_file_as_bytes(path);
    if (bytes.is_empty()) {
        impl->error = "Cannot read Rive file: " + path;
        return false;
    }
    rive::ImportResult result;
#ifdef _WIN32
    auto* factory = impl->backend.factory();
    if (!factory) {
        impl->error = String::utf8(impl->backend.error().c_str());
        return false;
    }
#else
    auto* factory = &impl->factory;
#endif
    impl->file = rive::File::import({bytes.ptr(), static_cast<size_t>(bytes.size())},
                                    factory, &result);
    if (!impl->file) {
        impl->error = "Rive import failed (" + String::num_int64(static_cast<int>(result)) + "): " + path;
        return false;
    }
    impl->artboard = impl->file->artboardNamed(artboard_name.utf8().get_data());
    if (!impl->artboard) {
        impl->error = "Missing Rive artboard: " + artboard_name;
        return false;
    }
    impl->machine = impl->artboard->stateMachineNamed(state_machine_name.utf8().get_data());
    if (!impl->machine) {
        impl->error = "Missing Rive state machine: " + state_machine_name;
        return false;
    }
    auto instance = impl->file->createDefaultViewModelInstance(impl->artboard.get());
    if (!instance) {
        impl->error = "Rive artboard has no default view model";
        impl->machine.reset();
        return false;
    }
    impl->model = rive::make_rcp<rive::ViewModelInstanceRuntime>(instance);
    const Array keys = initial_values.keys();
    for (int i = 0; i < keys.size(); ++i) {
        const String key = keys[i];
        const Variant value = initial_values[key];
        bool accepted = false;
        if (value.get_type() == Variant::BOOL) accepted = set_boolean(key, value);
        else if (value.get_type() == Variant::STRING) accepted = set_text(key, value);
        else if (value.get_type() == Variant::INT || value.get_type() == Variant::FLOAT)
            accepted = set_number(key, value);
        if (!accepted) {
            impl->error = "Invalid initial view model property: " + key;
            impl->machine.reset();
            return false;
        }
    }
    impl->machine->bindViewModelInstance(instance);
    return resize(Vector2i(std::lround(impl->artboard->width()),
                          std::lround(impl->artboard->height())));
}

bool RiveSurface::resize(Vector2i size) {
    if (!impl->artboard || size.x < 1 || size.y < 1 || size.x > 4096 || size.y > 4096) return false;
#ifdef _WIN32
    if (size == impl->size && impl->backend.ready()) return true;
    if (!impl->backend.resize(size.x, size.y)) {
        impl->error = String::utf8(impl->backend.error().c_str());
        return false;
    }
#else
    if (size == impl->size && impl->context) return true;
    if (impl->context) { CGContextRelease(impl->context); impl->context = nullptr; }
#endif
    impl->size = size;
    const size_t byte_count = static_cast<size_t>(size.x) * size.y * 4;
    impl->pixels.assign(byte_count, 0);
    impl->straight_pixels.resize(byte_count);
#ifndef _WIN32
    CGColorSpaceRef color_space = CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    impl->context = CGBitmapContextCreate(impl->pixels.data(), size.x, size.y, 8,
        size.x * 4, color_space, kCGBitmapByteOrder32Big | kCGImageAlphaPremultipliedLast);
    CGColorSpaceRelease(color_space);
    if (!impl->context) { impl->error = "Cannot allocate Rive rendering surface"; return false; }
#endif
    impl->image.unref();
    impl->texture.unref();
    impl->artboard->width(size.x);
    impl->artboard->height(size.y);
    impl->dirty = true;
    return true;
}

Vector2i RiveSurface::get_size() const { return impl->size; }
bool RiveSurface::advance(double seconds) {
    if (!is_loaded() || !std::isfinite(seconds) || seconds < 0) return false;
    const bool active = impl->dirty || impl->advancing || impl->machine->needsAdvance();
    if (!active) return false;
    // Artboard data converters can animate after the state machine has settled.
    // The aggregate return includes their work; needsAdvance() alone does not.
    impl->advancing = impl->machine->advanceAndApply(
        static_cast<float>(std::min(seconds, 0.1)));
    impl->dirty = false;
    return impl->render();
}
Ref<ImageTexture> RiveSurface::get_texture() const { return impl->texture; }
Ref<Image> RiveSurface::get_image() const { return impl->image; }

bool RiveSurface::set_boolean(const String &name, bool value) {
    auto *property = impl->model ? impl->model->propertyBoolean(name.utf8().get_data()) : nullptr;
    if (!property) return false;
    if (property->value() != value) { property->value(value); impl->dirty = true; }
    return true;
}
bool RiveSurface::get_boolean(const String &name) const {
    auto *property = impl->model ? impl->model->propertyBoolean(name.utf8().get_data()) : nullptr;
    return property && property->value();
}
bool RiveSurface::set_text(const String &name, const String &value) {
    auto *property = impl->model ? impl->model->propertyString(name.utf8().get_data()) : nullptr;
    if (!property) return false;
    const std::string text = value.utf8().get_data();
    if (property->value() != text) { property->value(text); impl->dirty = true; }
    return true;
}
String RiveSurface::get_text(const String &name) const {
    auto *property = impl->model ? impl->model->propertyString(name.utf8().get_data()) : nullptr;
    return property ? String::utf8(property->value().c_str()) : String();
}
bool RiveSurface::set_number(const String &name, double value) {
    if (!std::isfinite(value) || std::abs(value) > std::numeric_limits<float>::max()) return false;
    auto *property = impl->model ? impl->model->propertyNumber(name.utf8().get_data()) : nullptr;
    if (!property) return false;
    const float number = static_cast<float>(value);
    if (property->value() != number) { property->value(number); impl->dirty = true; }
    return true;
}
double RiveSurface::get_number(const String &name) const {
    auto *property = impl->model ? impl->model->propertyNumber(name.utf8().get_data()) : nullptr;
    return property ? property->value() : 0.0;
}
Rect2 RiveSurface::get_layout_rect(const String &name) const {
    if (!impl->artboard) return Rect2();
    auto *layout = impl->artboard->find<rive::LayoutComponent>(name.utf8().get_data());
    if (!layout) return Rect2();
    const auto bounds = layout->worldBounds();
    return Rect2(bounds.left(), bounds.top(), bounds.width(), bounds.height());
}
void RiveSurface::pointer_move(Vector2 position) {
    if (is_loaded()) { impl->machine->pointerMove({position.x, position.y}); impl->dirty = true; }
}
void RiveSurface::pointer_down(Vector2 position) {
    if (is_loaded()) { impl->machine->pointerDown({position.x, position.y}); impl->dirty = true; }
}
void RiveSurface::pointer_up(Vector2 position) {
    if (is_loaded()) { impl->machine->pointerUp({position.x, position.y}); impl->dirty = true; }
}
int64_t RiveSurface::get_render_count() const { return impl->render_count; }
double RiveSurface::get_last_render_ms() const { return impl->render_ms; }
