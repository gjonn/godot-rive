#ifdef _WIN32
#include "d3d_surface.hpp"
#include <rive/artboard.hpp>
#include <rive/renderer/texture.hpp>
#include <rive/renderer/rive_renderer.hpp>
#include <rive/renderer/d3d11/render_context_d3d_impl.hpp>
#include <cstring>
#include <cstdio>

using Microsoft::WRL::ComPtr;
using namespace rive::gpu;

namespace {
std::string hresult_error(const char* operation, HRESULT result) {
    char code[16];
    std::snprintf(code, sizeof(code), "0x%08lX", static_cast<unsigned long>(result));
    return std::string(operation) + " failed (" + code + ")";
}

// Surfaces are driven sequentially on Godot's main thread. Sharing the device
// and factory avoids allocating a GPU context and shader cache per HUD button.
struct Device {
    ComPtr<ID3D11Device> gpu;
    ComPtr<ID3D11DeviceContext> immediate;
    std::unique_ptr<RenderContext> context;
    std::string error;

    Device() {
        const D3D_FEATURE_LEVEL levels[] = {D3D_FEATURE_LEVEL_11_1, D3D_FEATURE_LEVEL_11_0};
        HRESULT result = E_FAIL;
        // WARP also supports rendering without a physical adapter (e.g. CI).
        for (auto driver : {D3D_DRIVER_TYPE_HARDWARE, D3D_DRIVER_TYPE_WARP}) {
            result = D3D11CreateDevice(nullptr, driver, nullptr, 0, levels, 2,
                D3D11_SDK_VERSION, gpu.ReleaseAndGetAddressOf(), nullptr,
                immediate.ReleaseAndGetAddressOf());
            if (SUCCEEDED(result)) {
                D3DContextOptions options;
                context = RenderContextD3DImpl::MakeContext(gpu, immediate, options);
                if (context) return;
            }
        }
        error = FAILED(result) ? hresult_error("D3D11CreateDevice", result)
                               : "Rive does not support this D3D11 device";
    }
};

std::shared_ptr<Device> shared_device() {
    static std::weak_ptr<Device> cached;
    auto device = cached.lock();
    if (!device) { device = std::make_shared<Device>(); cached = device; }
    return device;
}
}

struct D3DSurface::Impl {
    std::shared_ptr<Device> device = shared_device();
    rive::rcp<RenderTargetD3D> target;
    ComPtr<ID3D11Texture2D> color;
    ComPtr<ID3D11Texture2D> staging;
    int width = 0, height = 0;
    std::string error = device->error;
};

D3DSurface::D3DSurface() : impl(std::make_unique<Impl>()) {}
D3DSurface::~D3DSurface() = default;
rive::Factory* D3DSurface::factory() { return impl->device->context.get(); }
bool D3DSurface::ready() const { return impl->target != nullptr; }
const std::string& D3DSurface::error() const { return impl->error; }

bool D3DSurface::resize(int width, int height) {
    if (!factory()) return false;
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width = width;
    desc.Height = height;
    desc.MipLevels = desc.ArraySize = desc.SampleDesc.Count = 1;
    desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.Usage = D3D11_USAGE_DEFAULT;
    desc.BindFlags = D3D11_BIND_RENDER_TARGET;
    ComPtr<ID3D11Texture2D> color, staging;
    HRESULT result = impl->device->gpu->CreateTexture2D(&desc, nullptr, &color);
    if (FAILED(result)) { impl->error = hresult_error("Create Rive target", result); return false; }
    desc.Usage = D3D11_USAGE_STAGING;
    desc.BindFlags = 0;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    result = impl->device->gpu->CreateTexture2D(&desc, nullptr, &staging);
    if (FAILED(result)) { impl->error = hresult_error("Create Rive readback", result); return false; }
    auto* backend = impl->device->context->static_impl_cast<RenderContextD3DImpl>();
    auto target = backend->makeRenderTarget(width, height);
    target->setTargetTexture(color);
    impl->target = std::move(target);
    impl->color = std::move(color);
    impl->staging = std::move(staging);
    impl->width = width;
    impl->height = height;
    impl->error.clear();
    return true;
}

bool D3DSurface::render(rive::ArtboardInstance* artboard, std::vector<uint8_t>& pixels) {
    if (!ready()) return false;
    auto& device = *impl->device;
    RenderContext::FrameDescriptor frame;
    frame.renderTargetWidth = impl->width;
    frame.renderTargetHeight = impl->height;
    frame.clearColor = 0;
    device.context->beginFrame(frame);
    {
        rive::RiveRenderer renderer(device.context.get());
        artboard->draw(&renderer);
    }
    RenderContext::FlushResources resources;
    resources.renderTarget = impl->target.get();
    device.context->flush(resources);
    device.immediate->CopyResource(impl->staging.Get(), impl->color.Get());
    D3D11_MAPPED_SUBRESOURCE mapped{};
    const HRESULT result = device.immediate->Map(impl->staging.Get(), 0, D3D11_MAP_READ, 0, &mapped);
    if (FAILED(result)) { impl->error = hresult_error("Read Rive pixels", result); return false; }
    const size_t row_bytes = static_cast<size_t>(impl->width) * 4;
    pixels.resize(row_bytes * impl->height);
    for (int y = 0; y < impl->height; ++y) {
        std::memcpy(pixels.data() + y * row_bytes,
                    static_cast<const uint8_t*>(mapped.pData) + y * mapped.RowPitch, row_bytes);
    }
    device.immediate->Unmap(impl->staging.Get(), 0);
    return true;
}
#endif
