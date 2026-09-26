#!/usr/bin/env python3
"""Exercise dynamic resolution through patched production startup/callback code.

Usage: CXX=c++ python3 check-dynamic-resolution.py PATH_TO_PATCHED_GAMESCOPE_SOURCE
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


if len(sys.argv) != 2:
    raise SystemExit("usage: check-dynamic-resolution.py PATH_TO_PATCHED_GAMESCOPE_SOURCE")


def block(text, start):
    opening = text.index("{", start)
    depth = 0
    for end in range(opening, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return text[start:end + 1]
    raise AssertionError("unterminated production block")


def function(text, signature):
    return block(text, text.index(signature))


source = Path(sys.argv[1])
main = (source / "src/main.cpp").read_text()
backend = (source / "src/Backends/WaylandBackend.cpp").read_text()
steamcompmgr = (source / "src/steamcompmgr.cpp").read_text()
wlserver = (source / "src/wlserver.cpp").read_text()

for expected in [
    '{ "dynamic-resolution", no_argument, 0 },',
    '"  --dynamic-resolution           follow nested Wayland output size for Xwayland modes\\n"',
    'else if (strcmp(opt_name, "dynamic-resolution") == 0)',
]:
    assert expected in main, expected

startup_start = main.index("\tif ( g_nNestedHeight == 0 )")
startup_end = main.index("\n\tif ( !wlserver_init() )", startup_start)
startup = main[startup_start:startup_end]
assert startup.count("if ( g_bDynamicResolution )") == 1
assert startup.index("if ( g_bDynamicResolution )") < startup.index("g_nNestedWidth = g_nOutputWidth;", startup.index("if ( g_bDynamicResolution )"))
assert startup.index("g_nNestedWidth = g_nOutputWidth;", startup.index("if ( g_bDynamicResolution )")) < startup.index("g_nNestedHeight = g_nOutputHeight;", startup.index("if ( g_bDynamicResolution )"))

configure = function(backend, "    void CWaylandPlane::LibDecor_Frame_Configure(")
fractional = function(backend, "    void CWaylandPlane::Wayland_FractionalScale_PreferredScale(")
call = "wlserver_set_dynamic_resolution( g_nOutputWidth, g_nOutputHeight );"
assert backend.count(call) == 2
assert configure.count(call) == 1
assert configure.index("g_nOutputHeight = WaylandScaleToPhysical") < configure.index("if ( g_bDynamicResolution )") < configure.index(call) < configure.index("CommitLibDecor")
received = block(fractional, fractional.index("if ( m_bHasRecievedScale )"))
assert fractional.count(call) == 1 and call in received
assert received.index("g_nOutputHeight =") < received.index("if ( g_bDynamicResolution )") < received.index(call)

compatibility_gate = "if ( g_nXWaylandCount > 1 && !g_bDynamicResolution )"
assert steamcompmgr.count(compatibility_gate) == 1
compatibility_branch = block(steamcompmgr, steamcompmgr.index(compatibility_gate))
assert "wlserver_set_xwayland_server_mode( 0, g_nOutputWidth, g_nOutputHeight, g_nOutputRefresh );" in compatibility_branch

setter = function(wlserver, "void wlserver_set_dynamic_resolution(")
for expected in [
    "assert( wlserver_is_lock_held() );",
    "if ( g_nNestedWidth == w && g_nNestedHeight == h )",
    "gamescope_xwayland_server_t *server = wlserver_get_xwayland_server( i );",
    "wlserver_set_xwayland_server_mode( i, w, h, server->get_output()->refresh );",
]:
    assert expected in setter, expected
assert "g_nOutputRefresh" not in setter and "g_nNestedRefresh" not in setter

harness = f'''#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <tuple>
#include <vector>
using std::size_t;

int g_nOutputWidth = 1280;
int g_nOutputHeight = 800;
int g_nOutputRefresh = 144000;
int g_nNestedWidth = 1024;
int g_nNestedHeight = 576;
int g_nNestedRefresh = 0;
bool g_bDynamicResolution = false;
bool lock_held = false;
int lock_count = 0;
int unlock_count = 0;
int commit_count = 0;
int repaint_count = 0;

struct wlr_output {{ int refresh; }};
class gamescope_xwayland_server_t {{
public:
    explicit gamescope_xwayland_server_t(int refresh) : output{{refresh}} {{}}
    wlr_output *get_output() {{ return &output; }}
    wlr_output output;
}};
std::vector<gamescope_xwayland_server_t> servers;
gamescope_xwayland_server_t *wlserver_get_xwayland_server(size_t index) {{ return &servers.at(index); }}
struct {{ struct {{ std::vector<int> xwayland_servers; }} wlr; }} wlserver;
std::vector<std::tuple<size_t, int, int, int>> modes;
bool wlserver_is_lock_held() {{ return lock_held; }}
void wlserver_lock() {{ assert(!lock_held); lock_held = true; ++lock_count; }}
void wlserver_unlock() {{ assert(lock_held); lock_held = false; ++unlock_count; }}
void wlserver_set_xwayland_server_mode(size_t index, int width, int height, int refresh) {{
    assert(lock_held);
    servers.at(index).output.refresh = refresh;
    modes.emplace_back(index, width, height, refresh);
}}
void wlserver_set_dynamic_resolution(int, int);

struct libdecor_frame {{}};
enum libdecor_window_state {{ LIBDECOR_WINDOW_STATE_NONE }};
struct libdecor_configuration {{ int width; int height; }};
bool libdecor_configuration_get_window_state(libdecor_configuration *, libdecor_window_state *) {{ return false; }}
bool libdecor_configuration_get_content_size(libdecor_configuration *config, libdecor_frame *, int *width, int *height) {{
    *width = config->width;
    *height = config->height;
    return true;
}}
int WaylandScaleToLogical(int value, int32_t) {{ return value; }}
int WaylandScaleToPhysical(int value, int32_t) {{ return value; }}
void force_repaint() {{ ++repaint_count; }}

namespace gamescope {{
class CWaylandPlane {{
public:
    int32_t GetScale() const {{ return 1; }}
    void CommitLibDecor(libdecor_configuration *) {{ ++commit_count; }}
    void LibDecor_Frame_Configure(libdecor_frame *, libdecor_configuration *);
    libdecor_window_state m_eWindowState = LIBDECOR_WINDOW_STATE_NONE;
    libdecor_frame *m_pFrame = nullptr;
}};
{configure}
}}

{setter}

int initialize_nested() {{
{startup}
    return 0;
}}

int main() {{
    servers.emplace_back(60000);
    servers.emplace_back(75000);
    wlserver.wlr.xwayland_servers = {{ 0, 1 }};
    gamescope::CWaylandPlane plane;

    // Flag off: output events must not alter the fixed nested size.
    libdecor_configuration config{{ 1600, 900 }};
    assert(initialize_nested() == 0);
    plane.LibDecor_Frame_Configure(nullptr, &config);
    assert(g_nOutputWidth == 1600 && g_nOutputHeight == 900);
    assert(g_nNestedWidth == 1024 && g_nNestedHeight == 576);
    assert(modes.empty() && lock_count == 0 && unlock_count == 0);

    // Flag on: startup output dimensions override explicit -w/-h.
    g_bDynamicResolution = true;
    g_nOutputWidth = 1280;
    g_nOutputHeight = 800;
    g_nNestedWidth = 1024;
    g_nNestedHeight = 576;
    assert(initialize_nested() == 0);
    assert(g_nNestedWidth == 1280 && g_nNestedHeight == 800 && modes.empty());

    // An unchanged configure traverses the production callback but emits no mode.
    config = {{ 1280, 800 }};
    plane.LibDecor_Frame_Configure(nullptr, &config);
    assert(modes.empty());

    // With no explicit -r, a host at 144 Hz must not replace the existing
    // per-output 60/75 Hz modes during the first or later resolution changes.
    config = {{ 1920, 1080 }};
    plane.LibDecor_Frame_Configure(nullptr, &config);
    config = {{ 2560, 1440 }};
    plane.LibDecor_Frame_Configure(nullptr, &config);
    config = {{ 1280, 800 }};
    plane.LibDecor_Frame_Configure(nullptr, &config);
    assert(g_nNestedWidth == 1280 && g_nNestedHeight == 800);
    assert((modes == std::vector<std::tuple<size_t, int, int, int>>{{
        {{0, 1920, 1080, 60000}}, {{1, 1920, 1080, 75000}},
        {{0, 2560, 1440, 60000}}, {{1, 2560, 1440, 75000}},
        {{0, 1280, 800, 60000}}, {{1, 1280, 800, 75000}}
    }}));

    // A repeated configure remains coalesced after the downsize.
    plane.LibDecor_Frame_Configure(nullptr, &config);
    assert(modes.size() == 6);
    assert(!lock_held && lock_count == 5 && unlock_count == 5);
    assert(commit_count == 6 && repaint_count == 6);
}}
'''

with tempfile.TemporaryDirectory(prefix="gamescope-dynamic-resolution-check-") as directory:
    path = Path(directory)
    harness_path = path / "check.cpp"
    executable = path / "check"
    harness_path.write_text(harness)
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++20", str(harness_path), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)

print("Gamescope dynamic-resolution regression checks passed")
