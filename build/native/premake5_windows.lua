-- Build the pinned runtime and its D3D11 renderer without Unix build tools.
local rive_source = path.getabsolute('../../thirdparty/rive-cpp')
dofile(path.join(rive_source, 'premake5_v2.lua'))

filter({})
project('rive_pls_renderer')
    kind('StaticLib')
    includedirs({rive_source .. '/include', rive_source .. '/renderer/include',
                 rive_source .. '/renderer/src', rive_source .. '/decoders/include',
                 RIVE_BUILD_OUT .. '/include'})
    files({rive_source .. '/renderer/src/*.cpp', rive_source .. '/renderer/src/d3d/*.cpp',
           rive_source .. '/renderer/src/d3d11/*.cpp',
           rive_source .. '/renderer/src/ore/ore_binding_map.cpp',
           rive_source .. '/renderer/src/ore/ore_bind_group_layout.cpp'})

-- Match godot-cpp's static release CRT in both template configurations.
-- Rive's DEBUG changes class layouts; the wrapper also uses NDEBUG.
workspace('rive')
filter({})
    staticruntime('On')
    runtime('Release')
    buildoptions({'/MP' .. (os.getenv('RIVE_BUILD_JOBS') or '4')})
