#pragma once

#ifdef _WIN32
#include <memory>
#include <string>
#include <vector>
#include <cstdint>

namespace rive { class Factory; class ArtboardInstance; }

// Rive owns a separate D3D11 device. Readback keeps Godot renderer-independent.
class D3DSurface {
    struct Impl;
    std::unique_ptr<Impl> impl;
public:
    D3DSurface();
    ~D3DSurface();
    rive::Factory* factory();
    bool ready() const;
    bool resize(int width, int height);
    bool render(rive::ArtboardInstance*, std::vector<uint8_t>& pixels);
    const std::string& error() const;
};
#endif
