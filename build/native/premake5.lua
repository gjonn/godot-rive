-- Current Rive runtime with Apple's software vector renderer.
-- No GPU context is shared with Godot; the resulting transparent texture works
-- with Godot's Mobile, Forward+ and Compatibility renderers.
local runtime = path.getabsolute('../../thirdparty/rive-cpp')
dofile(path.join(runtime, 'premake5_v2.lua'))

project('rive_cg_renderer')
do
    kind('StaticLib')
    includedirs({runtime .. '/include', runtime .. '/cg_renderer/include'})
    files({runtime .. '/cg_renderer/src/**.cpp'})
end
