"""Windows build support: MSVC, Windows SDK and pinned Premake; no MSYS required."""
import concurrent.futures
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

PREMAKE_VERSION = "5.0.0-beta7"


def run(command, **kwargs):
    subprocess.run([str(value) for value in command], check=True, **kwargs)


def developer_environment():
    env = os.environ.copy()
    if shutil.which("cl") and shutil.which("fxc"):
        return env
    vswhere = Path(env.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / \
        "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output([
        vswhere, "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"
    ], text=True).strip()
    if not installation:
        raise RuntimeError("Install Visual Studio C++ Build Tools and a Windows SDK.")
    setup = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
    output = subprocess.check_output(
        f'cmd.exe /d /s /c ""{setup}" >nul && set"', text=True)
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            # os.environ is case-insensitive on Windows; a plain dict is not.
            prior = next((name for name in env if name.lower() == key.lower()), key)
            env[prior] = value
    return env


def build(args, root, build_dir, targets):
    env = developer_environment()
    # HarfBuzz's test fixture names exceed MAX_PATH in ordinary checkout paths.
    # Scope long-path support to child git commands, never change global config.
    config_count = int(env.get("GIT_CONFIG_COUNT", "0"))
    env[f"GIT_CONFIG_KEY_{config_count}"] = "core.longpaths"
    env[f"GIT_CONFIG_VALUE_{config_count}"] = "true"
    env["GIT_CONFIG_COUNT"] = str(config_count + 1)
    env["PREMAKE_PATH"] = str(root / "thirdparty/rive-cpp/build")
    env["RIVE_BUILD_JOBS"] = str(args.jobs)
    runtime = root / "thirdparty/rive-cpp"
    dependencies = build_dir / "dependencies"
    dependencies.mkdir(parents=True, exist_ok=True)
    premake_dir = dependencies / f"premake-{PREMAKE_VERSION}"
    premake = premake_dir / "premake5.exe"
    if not premake.exists():
        archive = dependencies / "premake.zip"
        url = f"https://github.com/premake/premake-core/releases/download/v{PREMAKE_VERSION}/premake-{PREMAKE_VERSION}-windows.zip"
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as package:
            package.extractall(premake_dir)
    ply = dependencies / "dabeaz_ply_3.11"
    if not ply.exists():
        run(["git", "clone", "--depth", "1", "--branch", "3.11",
             "https://github.com/dabeaz/ply.git", ply], env=env)
    # Exactly the shader set/flags in the pinned renderer's Makefile. Run
    # natively so Windows builds do not require make, sh or Python aliases.
    shaders = runtime / "renderer/src/shaders"
    generated = build_dir / "out/windows_release/include/generated/shaders"
    generated.mkdir(parents=True, exist_ok=True)
    inputs = sorted(path for pattern in ("*.glsl", "*.vert", "*.frag")
                    for path in shaders.glob(pattern))
    fingerprint = hashlib.sha256()
    for source in [shaders / "minify.py", *inputs, *sorted((shaders / "d3d").glob("*.hlsl"))]:
        fingerprint.update(source.read_bytes())
    stamp = generated / "windows.sha256"
    if not stamp.exists() or stamp.read_text() != fingerprint.hexdigest():
        run([sys.executable, shaders / "minify.py", "--msvc", "-p", ply, "-o", generated,
             *[path.name for path in inputs]], cwd=shaders, env=env)
        (generated / "d3d").mkdir(exist_ok=True)
        fxc = shutil.which("fxc", path=env.get("Path", env.get("PATH")))
        if not fxc:
            raise RuntimeError("fxc.exe is missing. Install the Windows SDK.")
        commands = []
        for source in sorted((shaders / "d3d").glob("*.hlsl")):
            for stage, define, profile in (("vert", "VERTEX", "vs_5_0"),
                                           ("frag", "FRAGMENT", "ps_5_0")):
                if source.stem == "render_atlas" and stage == "frag":
                    continue  # Upstream's phony target; fill/stroke variants below.
                commands.append([fxc, "/nologo", "/D", define, "/I", generated,
                                 "/T", profile, "/Fh", generated / f"d3d/{source.stem}.{stage}.h", source])
        for suffix in ("stroke", "fill"):
            commands.append([fxc, "/nologo", "/D", "FRAGMENT", "/D", f"ATLAS_FEATHERED_{suffix.upper()}",
                             "/I", generated, "/T", "ps_5_0", "/Fh",
                             generated / f"d3d/render_atlas_{suffix}.frag.h", shaders / "d3d/render_atlas.hlsl"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            for future in [executor.submit(run, command, env=env) for command in commands]:
                future.result()
        stamp.write_text(fingerprint.hexdigest())
    run([premake, "--file=premake5_windows.lua", "vs2022", "--config=release",
         "--out=out/windows_release", "--arch=x64", "--toolset=msc", "--no-lto",
         "--with_rive_text", "--with_rive_layout"], cwd=build_dir, env=env)
    msbuild = shutil.which("MSBuild.exe", path=env.get("Path", env.get("PATH")))
    if not msbuild:
        candidate = Path(env.get("VSINSTALLDIR", "")) / "MSBuild/Current/Bin/MSBuild.exe"
        if candidate.is_file():
            msbuild = candidate
    if not msbuild:
        raise RuntimeError("MSBuild.exe is missing from the C++ developer environment.")
    run([msbuild, build_dir / "out/windows_release/rive.sln", f"/m:{args.jobs}",
         "/t:rive;rive_harfbuzz;rive_sheenbidi;rive_yoga;rive_pls_renderer",
         "/p:Configuration=default", "/p:Platform=x64", "/verbosity:minimal", "/nologo"], env=env)
    for target in targets:
        run([sys.executable, "-m", "SCons", "platform=windows", "arch=x86_64",
             "use_static_cpp=yes", f"target=template_{target}", "build_profile=build_profile.json",
             f"-j{args.jobs}"], cwd=build_dir, env=env)
