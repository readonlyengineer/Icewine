#!/usr/bin/env python3
"""Exercise the patched production handlers with an in-memory seat (no GPU/VM).

Usage: CXX=c++ python3 check-focus.py /path/to/patched/gamescope/source
This checks routing/state decisions, not wlroots/Xwayland wire behaviour.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
server = (source / 'src/wlserver.cpp').read_text()
backend = (source / 'src/Backends/WaylandBackend.cpp').read_text()
def function(text, signature, indent=''):
    start = text.index(signature)
    end = text.index('\n' + indent + '}', start) + len(indent) + 2
    return text[start:end]

# Use the production initialization; failed Wayland init must leave SDL usable.
init = function(backend, '    bool CWaylandBackend::Init()', '    ')
gate = 'wlserver.nested_keyboard_focus = false;'
assert init.rindex('return false;') < init.index(gate) < init.rindex('return true;')
methods = '\n'.join(function(server, name) for name in [
    'void wlserver_keyboardfocus(',
    'void wlserver_nested_keyboard_leave(',
    'bool wlserver_nested_keyboard_enter(',
    'bool wlserver_nested_keyboard_modifiers(',
    'void wlserver_nested_key(',
]) + '\n' + '\n'.join(function(backend, name, '    ') for name in [
    '    void CWaylandInputThread::HandleKey(',
    '    void CWaylandInputThread::Wayland_Keyboard_Enter(',
    '    void CWaylandInputThread::LeaveKeyboard(',
    '    void CWaylandInputThread::Wayland_Keyboard_Key(',
    '    void CWaylandInputThread::Wayland_Keyboard_Modifiers(',
])

support = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <optional>
#include <unordered_set>
#include <vector>
#include <linux/input-event-codes.h>
using std::size_t;
enum wl_keyboard_key_state { WL_KEYBOARD_KEY_STATE_RELEASED, WL_KEYBOARD_KEY_STATE_PRESSED };
constexpr size_t WLR_KEYBOARD_KEYS_CAP = 32;
struct wl_keyboard {};
struct wl_surface {};
struct wl_array { size_t size; void *data; };
struct xkb_keymap {};
unsigned xkb_keymap_min_keycode(xkb_keymap *) { return 8; }
unsigned xkb_keymap_max_keycode(xkb_keymap *) { return 255; }
struct wlr_keyboard_modifiers { uint32_t depressed=0, latched=0, locked=0, group=0; };
struct wlr_keyboard { xkb_keymap *keymap=nullptr; uint32_t keycodes[32]={}; size_t num_keycodes=0; wlr_keyboard_modifiers modifiers; };
struct wlr_keyboard_key_event { uint32_t time_msec, keycode; bool update_state; wl_keyboard_key_state state; };
struct wlr_surface {};
struct Event { char kind; uint32_t key=0; int state=0; std::vector<uint32_t> keys; wlr_keyboard_modifiers mods; };
struct Seat { wlr_surface *focus=nullptr; wlr_keyboard *keyboard=nullptr; std::vector<Event> events; };
struct Server {
    struct { Seat *seat; wlr_keyboard *virtual_keyboard_device; } wlr;
    wlr_surface *kb_focus_surface=nullptr;
    bool nested_keyboard_focus=true;
    void *constraints=nullptr;
    std::map<std::pair<wlr_keyboard *, uint32_t>, uint32_t> mapPressedHotkeyKeys;
} wlserver;
bool wlserver_is_lock_held() { return true; }
void wlserver_lock() {}
void wlserver_unlock() {}
void bump_input_counter() {}
struct Logger { void errorf(const char *) {} } wl_log, xdg_log;
bool consumeDown=false, consumeUp=false;
int hotkeyCalls=0;
bool wlserver_process_hotkeys(wlr_keyboard *, uint32_t, bool press) {
    ++hotkeyCalls;
    return press ? consumeDown : consumeUp;
}
void wlr_keyboard_notify_key(wlr_keyboard *k, wlr_keyboard_key_event *e) {
    assert(!e->update_state);
    auto end=k->keycodes+k->num_keycodes;
    auto p=std::find(k->keycodes,end,e->keycode);
    if(e->state && p==end) { assert(k->num_keycodes<32); k->keycodes[k->num_keycodes++]=e->keycode; }
    if(!e->state && p!=end) { std::move(p+1,end,p); --k->num_keycodes; }
}
void wlr_keyboard_notify_modifiers(wlr_keyboard *k,uint32_t d,uint32_t l,uint32_t lock,uint32_t g) { k->modifiers={d,l,lock,g}; }
bool wlr_keyboard_set_keymap(wlr_keyboard *k,xkb_keymap *map) { k->keymap=map; return true; }
void wlr_seat_set_keyboard(Seat *s,wlr_keyboard *k) { s->keyboard=k; }
wlr_keyboard *wlr_seat_get_keyboard(Seat *s) { return s->keyboard; }
void wlr_seat_keyboard_notify_clear_focus(Seat *s) { if(s->focus) s->events.push_back({'L'}); s->focus=nullptr; }
void wlr_seat_keyboard_notify_enter(Seat *s,wlr_surface *p,const uint32_t *keys,size_t n,const wlr_keyboard_modifiers *mods) {
    assert(p);
    if(s->focus==p) return;
    wlr_seat_keyboard_notify_clear_focus(s);
    s->focus=p;
    Event e{'E'};
    if(n) e.keys.assign(keys,keys+n);
    if(mods) e.mods=*mods;
    s->events.push_back(e);
}
void wlr_seat_keyboard_notify_modifiers(Seat *s,const wlr_keyboard_modifiers *mods) { if(s->focus) { Event e{'M'}; e.mods=*mods; s->events.push_back(e); } }
void wlr_seat_keyboard_notify_key(Seat *s,uint32_t,uint32_t key,int state) { if(s->focus) s->events.push_back({'K',key,state}); }
struct SurfaceInfo { void *xdg_surface; };
SurfaceInfo *get_wl_surface_info(wlr_surface *) { return nullptr; }
struct XdgSurface { void *toplevel; };
XdgSurface *wlr_xdg_surface_try_from_wlr_surface(wlr_surface *) { return nullptr; }
void wlr_xdg_toplevel_set_activated(void *,bool) {}
struct wlr_pointer_constraint_v1 {};
wlr_pointer_constraint_v1 *wlr_pointer_constraints_v1_constraint_for_surface(void *,wlr_surface *,Seat *) { return nullptr; }
void wlserver_constrain_cursor(wlr_pointer_constraint_v1 *) {}
void wlserver_keyboardfocus(wlr_surface *,bool=true);
void wlserver_nested_key(uint32_t,bool,uint32_t,bool=true);
bool IsGamescopeToplevel(wl_surface *s) { return s!=nullptr; }
constexpr int GAMESCOPE_WAYLAND_MOD_META=0;
enum class GamescopeUpscaleFilter { PIXEL, LINEAR, FSR, NIS };
GamescopeUpscaleFilter g_wantedUpscaleFilter=GamescopeUpscaleFilter::LINEAR;
int g_upscaleFilterSharpness=0;
bool g_bFullscreen=false;
int fullscreenActions=0;
struct CWaylandConnector { void SetFullscreen(bool) { ++fullscreenActions; } } connector;
struct Backend { CWaylandConnector *GetCurrentConnector() { return &connector; } } backendObject;
namespace gamescope { struct CScreenshotManager { static CScreenshotManager &Get() { static CScreenshotManager s; return s; } void TakeScreenshot(bool) {} }; }
struct CWaylandInputThread {
    bool m_bKeyboardEntered=false, m_bKeyboardEnterPending=false;
    uint32_t m_uKeyModifiers=0, m_uFakeTimestamp=0, m_uModMask[1]={64};
    wlr_keyboard_modifiers m_KeyboardModifiers={};
    std::unordered_set<uint32_t> m_uScancodesHeld, m_uInheritedScancodes, m_uShortcutScancodes;
    std::optional<double> m_ofPendingCursorX, m_ofPendingCursorY;
    void *m_pPointer=nullptr;
    xkb_keymap *m_pXkbKeymap=nullptr;
    Backend *m_pBackend=&backendObject;
    void HandleKey(uint32_t,bool);
    void LeaveKeyboard();
    void Wayland_Keyboard_Enter(wl_keyboard *,uint32_t,wl_surface *,wl_array *);
    void Wayland_Keyboard_Key(wl_keyboard *,uint32_t,uint32_t,uint32_t,uint32_t);
    void Wayland_Keyboard_Modifiers(wl_keyboard *,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
    void Wayland_Pointer_Motion(void *,uint32_t,double,double) {}
};
'''
checks = r'''
int main() {
    Seat seat;
    wlr_keyboard keyboard;
    xkb_keymap map;
    wlr_surface first, second;
    wl_surface outer;
    wlserver.wlr={&seat,&keyboard};
    INITIAL_GATE
    wlserver_keyboardfocus(&first);
    assert(!seat.focus); // Initially unfocused host must not focus a client.
    CWaylandInputThread input;
    input.m_pXkbKeymap=&map;
    auto enter=[&](std::vector<uint32_t> keys,uint32_t mods=0) {
        wl_array a{keys.size()*sizeof(uint32_t),keys.data()};
        input.Wayland_Keyboard_Enter(nullptr,0,&outer,&a);
        assert(!seat.focus); // Wait for the matching modifier snapshot.
        input.Wayland_Keyboard_Modifiers(nullptr,0,mods,0,2,1);
    };
    auto key=[&](uint32_t k,bool down) { input.Wayland_Keyboard_Key(nullptr,0,0,k,down); };
    auto keyEvents=[&]() { return std::count_if(seat.events.begin(),seat.events.end(),[](const Event &e){return e.kind=='K';}); };
    auto held=[&](uint32_t k) { return std::find(keyboard.keycodes,keyboard.keycodes+keyboard.num_keycodes,k)!=keyboard.keycodes+keyboard.num_keycodes; };

    enter({KEY_ENTER,KEY_LEFTSHIFT},1);
    assert(seat.focus==&first && keyEvents()==0);
    const auto &snapshot=seat.events.back();
    assert(snapshot.kind=='E' && snapshot.keys.size()==2);
    assert(snapshot.mods.depressed==1 && snapshot.mods.locked==2 && snapshot.mods.group==1);
    int calls=hotkeyCalls;
    key(KEY_ENTER,false);
    assert(keyEvents()==1 && hotkeyCalls==calls && !held(KEY_ENTER));
    key(KEY_ENTER,true); key(KEY_ENTER,false);
    assert(keyEvents()==3 && !held(KEY_ENTER));
    input.LeaveKeyboard();
    assert(!seat.focus && !keyboard.num_keycodes && keyEvents()==3);
    wlserver_keyboardfocus(&second);
    assert(!seat.focus && wlserver.kb_focus_surface==&second);
    enter({KEY_W});
    assert(seat.focus==&second && held(KEY_W));
    wlserver_keyboardfocus(&first);
    assert(seat.events.back().kind=='E' && seat.events.back().keys==std::vector<uint32_t>{KEY_W});
    input.LeaveKeyboard();
    wlserver.kb_focus_surface=nullptr; // Existing surface-destruction hook.
    enter({});
    assert(!seat.focus);
    wlserver_keyboardfocus(&first);
    assert(seat.focus==&first);

    seat.events.clear();
    consumeDown=true;
    key(KEY_A,true);
    assert(!held(KEY_A) && keyEvents()==0);
    consumeDown=false;
    key(KEY_A,false);
    assert(keyEvents()==0);
    key(KEY_A,true);
    consumeUp=true;
    key(KEY_A,false);
    assert(!held(KEY_A) && keyEvents()==2);
    consumeUp=false;

    // Meta changes after an ordinary down must not swallow its release.
    key(KEY_F,true);
    input.Wayland_Keyboard_Modifiers(nullptr,0,64,0,0,0);
    key(KEY_F,false);
    assert(!held(KEY_F) && fullscreenActions==0);
    // A real shortcut must consume its pair even when Meta is released first.
    auto before=keyEvents();
    key(KEY_F,true);
    input.Wayland_Keyboard_Modifiers(nullptr,0,0,0,0,0);
    key(KEY_F,false);
    assert(keyEvents()==before && fullscreenActions==1 && !held(KEY_F));
    // An inherited shortcut key is state, not a shortcut awaiting completion.
    enter({KEY_F,KEY_LEFTMETA},64);
    key(KEY_F,false);
    assert(fullscreenActions==1 && !held(KEY_F));
    input.LeaveKeyboard();
    assert(!input.m_uShortcutScancodes.size());

    std::vector<uint32_t> tooMany(33,KEY_A);
    wl_array invalid{tooMany.size()*sizeof(uint32_t),tooMany.data()};
    input.Wayland_Keyboard_Enter(nullptr,0,&outer,&invalid);
    assert(!input.m_bKeyboardEntered && !seat.focus);
}
'''.replace('INITIAL_GATE',gate)
with tempfile.TemporaryDirectory(prefix='gamescope-focus-check-') as directory:
    cpp=Path(directory)/'check.cpp'
    executable=Path(directory)/'check'
    cpp.write_text(support+'\n'+methods+'\n'+checks)
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-Wall','-Wextra',
                    '-Wno-unused-parameter','-Wno-missing-field-initializers',str(cpp),'-o',str(executable)],check=True)
    subprocess.run([str(executable)],check=True)
print('Gamescope focus/state regression checks passed')
