#!/usr/bin/env python3
"""Exercise the actual Topbar surface/bindings offscreen; no compositor proof.
Run: python3 tests/bar-geometry.py . (qs on PATH).
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from qml_fixture import theme_fixture

source = Path(sys.argv[1]).resolve()
native = (source / 'quickshell/modules/Topbar.qml').read_text()
# Extract intact production blocks as the window-switcher fixture does. Native
# panels cannot be mapped offscreen; invisible Wayland request objects expose
# the shipped native properties, with Item stand-ins for compositor arrangement.
def block(marker):
    start = native.index(marker)
    opening = native.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (native[end] == '{') - (native[end] == '}')
        end += 1
    return native[start:end]

surface = block('                Rectangle {\n                    id: surface')
properties = '\n'.join(line for line in native.splitlines() if re.match(
    r'    readonly property (?:int|bool) (?:barHeight|barGap|barExtent|shadowExtent|fullBar|floatingBar|bottomBar):', line))
def binding(name, text=native):
    match = re.search(r'^ *' + re.escape(name) + r': (.+)$', text, re.M)
    value = match[1]
    for line in text[match.end():].splitlines()[1:]:
        if value.count('(') == value.count(')'): break
        value += '\n' + line
    return value
bar_window = block('            property PanelWindow barWindow: PanelWindow')
# Exercise the compiled Wayland request objects without mapping a native window.
# Offscreen Items below receive the sizes implied by those native requests.
def anchors(text):
    return re.search(r'anchors \{[^}]+\}', text)[0]
overlay = native[native.index('            screen: modelData'):]
popout = native.split('id: statusPopout')[1]
qml = '''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Effects
import QtTest
import Quickshell
import Quickshell.Wayland
import Quickshell.Wayland._WlrLayerShell as Native
import qs.config as Config
import "icewine/modules/topbar" as Bar
import "icewine/modules/ShellState.js" as State
import "icewine/theme" as Theme
ShellRoot {
    id: root
    property bool sessionLocked: false
    property bool fullWidth: false
    property bool radialVisible: false
    property var ui: State.initial()
    property string hoveredScreen: ""
    readonly property bool barVisible: __BAR_VISIBLE__
    property bool instantBarHide: true
    property int shadowDrop: 4
    property bool layoutsEnabled: true
    property var player: testPlayer
    property string openedPage: ""
    property bool openedEngaged: false
    property int raiseCount: 0
    QtObject {
        id: testPlayer
        property string trackTitle: "A track with a long title for overflow geometry"
        property string identity: "Fixture player"
        property bool isPlaying: true
        property bool canRaise: true
    }
    property var notificationService: ({count: 0, highestUrgency: 0, doNotDisturb: false, pulseToken: 0})
    property var compositor: ({
        monitorFor: screen => ({activeWorkspace: {id: 1}}),
        workspaceIdsForMonitor: monitor => [1,2,3,4,5,6,7,8,9,10],
        toplevelsForWorkspace: id => [], activateWorkspace: id => {}
    })
    function raiseMedia() { raiseCount++ }
    function openWidget(page, engaged, screen) { openedPage = page; openedEngaged = engaged }
    __PROPERTIES__
    property int foreignTop: 0
    property int foreignBottom: 0
    Native.WlrLayershell {
        id: barRequest
        visible: false
        layer: __BAR_LAYER__
        keyboardFocus: __BAR_FOCUS__
        __BAR_ANCHORS__
        implicitHeight: __BAR_HEIGHT__
        exclusiveZone: __BAR_ZONE__
        __BAR_MARGINS__
    }
    Native.WlrLayershell {
        id: overlayRequest
        visible: false
        layer: __OVERLAY_LAYER__
        __OVERLAY_ANCHORS__
        exclusionMode: __OVERLAY_MODE__
        exclusiveZone: __OVERLAY_ZONE__
        __OVERLAY_MARGINS__
    }
    QtObject { id: clock; property date date: new Date(2026, 9, 18, 12, 30) }
    Window {
        id: window
        width: panel.width; height: panel.height
        visible: true
        Item {
            id: panel
            width: 1280; height: 800
            property var screen: ({name: "fixture"})
            readonly property int reservation: __RESERVATION__
            readonly property string hoverPage: __HOVER_PAGE__
            Item {
                id: barHost
                width: panel.width
                height: barRequest.implicitHeight
                y: barRequest.anchors.bottom ? panel.height - root.foreignBottom - height : root.foreignTop
                __EDGE__
                __SURFACE__
            }
            Item {
                id: input
                y: root.foreignTop + (!root.bottomBar ? panel.reservation : 0) + overlayRequest.margins.top + aboveInset
                readonly property int aboveInset: __CONTENT_INSET__
                width: panel.width
                height: panel.height - root.foreignTop - root.foreignBottom - panel.reservation
                    - overlayRequest.margins.top - overlayRequest.margins.bottom - aboveInset
            Rectangle {
                id: statusPopout
                property int backgroundCount: 0
                property bool backgroundAttention: false
                implicitHeight: 620
                width: Math.min(380, panel.width - 16)
                x: __POPOUT_X__
                y: __POPOUT_Y__
                height: __POPOUT_HEIGHT__
            }
            }
        }
        Timer {
            interval: 100; running: true
            onTriggered: {
                try {
                    if (!root.barVisible && (surface.opacity !== 0 || surface.y !== (root.bottomBar ? barHost.height : -surface.height)))
                        throw new Error("Hidden startup surface did not settle")
                    __TEST_CALL__
                }
                catch (error) { console.error(error + "\\n" + error.stack); Qt.exit(1) }
            }
        }
        TestCase {
            id: checks
            name: "BarGeometry"
            when: false
            function fuzzy(actual, expected, tolerance, label) {
                if (!Number.isFinite(actual) || !Number.isFinite(expected) || Math.abs(actual - expected) > tolerance)
                    throw new Error((label || "Geometry") + ": actual " + actual + ", expected " + expected)
            }
            function transitions() {
                root.instantBarHide = false
                for (const behaviour of ["keyboard", "keyboard-mouse", "toggle", "always"])
                for (const location of ["above", "top", "bottom"]) {
                    Config.Settings.widgetSelections = {barBehaviour: behaviour, barLocation: location}
                    function send(type) { root.ui = State.reduce(root.ui, {type: type, behaviour: behaviour}) }
                    function settled(visible) {
                        compare(root.barVisible, visible)
                        compare(barRequest.layer, location === "above" ? WlrLayer.Overlay : WlrLayer.Top)
                        compare(barRequest.keyboardFocus, WlrKeyboardFocus.None)
                        compare(overlayRequest.layer, WlrLayer.Overlay, "Explicit widgets and radial retain their overlay")
                        tryCompare(surface, "opacity", visible ? 1 : 0)
                        tryCompare(surface, "y", root.bottomBar ? (visible
                            ? barHost.height - surface.height - root.barGap : barHost.height)
                            : (visible ? root.barGap : -surface.height))
                        compare(panel.reservation, visible && location !== "above" ? root.barExtent : 0)
                    }
                    root.ui = State.initial()
                    send("press"); send("press") // Repeat must not reverse a latch.
                    settled(true)
                    send("release"); send("release") // Both chord release orders end held intent.
                    settled(behaviour === "toggle" || behaviour === "always")
                    // Interrupt an animation without waiting for its old target.
                    send("press"); wait(10); send("release"); send("press"); send("release")
                    root.hoveredScreen = "fixture"
                    settled(true)
                    root.hoveredScreen = ""
                    settled(behaviour === "toggle" || behaviour === "always")
                    root.sessionLocked = true
                    settled(false)
                    root.sessionLocked = false
                    send("reset")
                    settled(behaviour === "always")
                }
                root.instantBarHide = true
            }
            function capture_animations() {
                root.instantBarHide = false
                for (const location of ["above", "top", "bottom"])
                for (const alreadyClosing of [true, false]) {
                    Config.Settings.widgetSelections = {barBehaviour: "toggle", barLocation: location}
                    root.ui = State.reduce(State.initial(), {type: "press", behaviour: "toggle"})
                    tryCompare(surface, "opacity", 1)
                    const shownY = root.bottomBar ? barHost.height - surface.height - root.barGap : root.barGap
                    tryCompare(surface, "y", shownY)
                    root.ui = State.reduce(root.ui, {type: "hide"})
                    if (alreadyClosing) tryVerify(() => surface.opacity > 0 && surface.opacity < 1)
                    const hiddenY = root.bottomBar ? barHost.height : -surface.height
                    // Target remains hidden; changing duration alone cannot finish the old job.
                    root.instantBarHide = true
                    if (surface.opacity !== 0 || surface.y !== hiddenY)
                        throw new Error("CAPTURE_BAR_NOT_FINISHED: " + location + ": " + surface.y + "/" + surface.opacity)
                    root.instantBarHide = false
                    wait(200)
                    compare(surface.opacity, 0); compare(surface.y, hiddenY)
                    root.ui = State.reduce(State.initial(), {type: "press", behaviour: "toggle"})
                    tryVerify(() => surface.opacity > 0 && surface.opacity < 1)
                    tryCompare(surface, "opacity", 1)
                    tryCompare(surface, "y", shownY)
                    root.ui = State.reduce(root.ui, {type: "hide"})
                    tryVerify(() => surface.opacity > 0 && surface.opacity < 1)
                    tryCompare(surface, "opacity", 0)
                    tryCompare(surface, "y", hiddenY)
                }
                root.instantBarHide = true
            }
            function native_geometry() {
                // Captured failure: 2880x1800 at 1.5x => logical 1920x1200;
                // the old 1238-high overlay placed the bottom surface at y=1200.
                panel.width = 1920; panel.height = 1200
                for (const location of ["above", "top", "bottom"])
                for (const style of ["anchored", "floating"])
                for (const percent of [50, 100])
                for (const zones of [[0, 0], [24, 260]]) {
                    Config.Settings.widgetSelections = {barBehaviour: "toggle", barLocation: location,
                        barStyle: style, barWidth: percent}
                    root.foreignTop = zones[0]; root.foreignBottom = zones[1]
                    root.ui = State.reduce(State.initial(), {type: "press", behaviour: Config.Settings.barBehaviour})
                    wait(1)
                    compare(overlayRequest.exclusionMode, ExclusionMode.Normal)
                    compare(overlayRequest.exclusiveZone, 0)
                    verify(overlayRequest.anchors.top && overlayRequest.anchors.bottom
                        && overlayRequest.anchors.left && overlayRequest.anchors.right)
                    verify(barRequest.anchors.left && barRequest.anchors.right)
                    compare(barRequest.anchors.top, location !== "bottom")
                    compare(barRequest.anchors.bottom, location === "bottom")
                    compare(barRequest.exclusiveZone, panel.reservation)
                    const top = barHost.y + surface.y
                    const bottom = top + surface.height
                    verify(top >= zones[0] && bottom <= panel.height - zones[1],
                        "Bar remains inside the native available output, including foreign/OSK zones")
                    verify(barHost.height >= root.barExtent && barHost.height < panel.height)
                    compare(location === "bottom" ? bottom + root.barGap : top - root.barGap,
                        location === "bottom" ? panel.height - zones[1] : zones[0])
                    const popupTop = input.y + statusPopout.y
                    const popupBottom = popupTop + statusPopout.height
                    verify(popupTop >= zones[0] && popupBottom <= panel.height - zones[1])
                    if (location === "bottom") verify(popupBottom <= top - 4)
                    else verify(popupTop >= bottom + 4)
                    compare(barHost.y + edge.y, location === "bottom"
                        ? panel.height - zones[1] - 1 : zones[0])
                    root.ui = State.reduce(State.initial(), {type: "hide"})
                    wait(1)
                    compare(barRequest.exclusiveZone, 0)
                    compare(input.height, panel.height - zones[0] - zones[1] - input.aboveInset)
                }
                root.foreignTop = 0; root.foreignBottom = 0
            }
            function test_geometry() {
                wait(100) // Let the real Settings FileView finish its initial read.
                for (const size of [[1920, 1200], [1280, 800], [640, 480], [853, 600]]) {
                    panel.width = size[0]; panel.height = size[1]
                    for (const behaviour of ["keyboard", "keyboard-mouse", "toggle", "always"])
                    for (const location of ["above", "top", "bottom"])
                    for (const style of ["anchored", "floating"])
                    for (const percent of [50, 99, 100]) {
                        Config.Settings.widgetSelections = {barBehaviour: behaviour, barLocation: location,
                            barWidth: percent, barStyle: style}
                        root.ui = State.reduce(State.initial(), {type: "press", behaviour: Config.Settings.barBehaviour})
                        wait(1)
                        const gap = style === "floating" ? 4 : 0
                        fuzzy(surface.width, panel.width * percent / 100, 0.001)
                        fuzzy(surface.x, (panel.width - surface.width) / 2, 0.001, "Exact logical output centring")
                        compare(surface.y, location === "bottom" ? barHost.height - 38 - gap : gap)
                        const topRadius = percent === 100 ? 0 : style === "floating" ? 19 : location === "bottom" ? 10 : 0
                        const bottomRadius = percent === 100 ? 0 : style === "floating" ? 19 : location === "bottom" ? 0 : 10
                        compare(surface.topLeftRadius, topRadius); compare(surface.topRightRadius, topRadius)
                        compare(surface.bottomLeftRadius, bottomRadius); compare(surface.bottomRightRadius, bottomRadius)
                        compare(panel.reservation, location === "above" ? 0 : 38 + gap)
                        verify(statusPopout.y >= 0 && statusPopout.y + statusPopout.height <= panel.height)
                        verify(statusPopout.x >= 0 && statusPopout.x + statusPopout.width <= panel.width)
                        // Real content rows stay inside the bar and clear the clock.
                        verify(workspaceScroll.x + workspaceScroll.width + 4 <= barClock.x + 0.01)
                        verify(statusScroll.x >= barClock.x + barClock.width + 4 - 0.01)
                        verify(workspaceScroll.x >= 0 && statusScroll.x + statusScroll.width <= surface.width)
                        root.ui = State.reduce(State.initial(), {type: "hide"})
                        wait(1)
                        compare(panel.reservation, 0)
                        verify(surface.y + surface.height <= 0 || surface.y >= barHost.height)
                    }
                }
                native_geometry()
                transitions()
                capture_animations()
                // Media-leading stacks use the retained independent capsule and routing.
                panel.width = 1280
                Config.Settings.widgetSelections = {barWidth: 100}
                root.ui = State.reduce(State.initial(), {type: "press", behaviour: Config.Settings.barBehaviour})
                wait(200)
                verify(nowPlaying.visible)
                compare(nowPlaying.parent, statusIcons.parent)
                verify(nowPlaying.x + nowPlaying.width + 4 <= statusIcons.x)
                verify(!statusIcons.cardStacks.some(stack => stack.modules[0] === "media"))
                verify(logo.visible, "Launcher remains separate on the left")
                const content = nowPlaying.children[0]
                const icon = content.children[0].children[0]
                const title = content.children[1]
                compare(title.text, testPlayer.trackTitle)
                compare(icon.text, "")
                testPlayer.isPlaying = false
                testPlayer.trackTitle = "Updated track"
                wait(200)
                compare(title.text, "Updated track"); compare(icon.text, "")
                testPlayer.trackTitle = ""
                wait(200)
                compare(title.text, "Fixture player")
                mouseMove(nowPlaying, 10, 10)
                wait(50)
                compare(panel.hoverPage, "media")
                mouseClick(content.children[0], 12, 14)
                compare(root.openedPage, "media"); verify(root.openedEngaged)
                mouseClick(title, 10, 14)
                compare(root.raiseCount, 1)
                testPlayer.canRaise = false
                mouseClick(title, 10, 14)
                compare(root.raiseCount, 1)
                mouseMove(surface, surface.width / 2, 1)
                root.player = null
                wait(200)
                verify(!nowPlaying.visible); compare(nowPlaying.implicitWidth, 0)
                verify(panel.hoverPage !== "media")
                root.player = testPlayer
                for (const stacks of [[], [{id: "audio", modules: ["audio", "media"]}]]) {
                    Config.Settings.widgetSelections = {cardStacks: stacks}
                    wait(200)
                    verify(!nowPlaying.visible)
                    compare(statusIcons.cardStacks.length, stacks.length)
                    if (stacks.length) {
                        const button = statusIcons.children[0].children.find(item => item.page === "audio")
                        compare(button.page, "audio")
                        mouseMove(button, 10, 10)
                        wait(50)
                        compare(panel.hoverPage, "audio")
                        mouseClick(button, 10, 10)
                        compare(root.openedPage, "audio")
                    } else verify(!statusIcons.visible)
                }
                Config.Settings.widgetSelections = {cardStacks: [{id: "mixed", modules: ["media", "audio"]}]}
                wait(200)
                verify(nowPlaying.visible); verify(!statusIcons.visible)
                mouseMove(nowPlaying, 10, 10)
                wait(50)
                compare(panel.hoverPage, "media")
                // Native Flickables expose otherwise overflowing real controls by dragging.
                Config.Settings.widgetSelections = {barWidth: 50, barStyle: "floating"}
                panel.width = 640; root.ui = State.reduce(State.initial(), {type: "press", behaviour: Config.Settings.barBehaviour})
                wait(30)
                verify(workspaceScroll.contentWidth > workspaceScroll.width)
                verify(statusScroll.contentWidth > statusScroll.width)
                mouseDrag(workspaceScroll, workspaceScroll.width - 5, 14, -50, 0, Qt.LeftButton)
                wait(100)
                verify(workspaceScroll.contentX > 0, "Workspace controls can be reached by dragging")
                mouseDrag(statusScroll, statusScroll.width - 5, 14, -50, 0, Qt.LeftButton)
                wait(100)
                verify(statusScroll.contentX > 0, "Status controls can be reached by dragging")
                for (const controller of ["fullWidth", "radialVisible"]) {
                    root[controller] = true
                    wait(1)
                    compare(surface.width, panel.width); compare(root.barGap, 0)
                    compare(surface.topLeftRadius, 0); compare(surface.bottomLeftRadius, 0)
                    root[controller] = false
                }
                console.log("BAR_GEOMETRY_PASSED")
                Qt.quit()
            }
        }
    }
}
'''
for key, value in {'TEST_CALL': 'checks.capture_animations(); console.log(\"BAR_GEOMETRY_PASSED\"); Qt.quit()' if '--capture-only' in sys.argv else 'checks.test_geometry()', 'PROPERTIES': properties, 'SURFACE': surface,
                   'EDGE': block('                Item {\n                    id: edge'),
                   'BAR_LAYER': binding('WlrLayershell.layer', bar_window),
                   'BAR_FOCUS': binding('WlrLayershell.keyboardFocus', bar_window),
                   'OVERLAY_LAYER': binding('WlrLayershell.layer', overlay),
                   'BAR_ANCHORS': anchors(bar_window),
                   'BAR_HEIGHT': binding('implicitHeight', bar_window),
                   'BAR_MARGINS': '\n'.join(re.findall(r'^ *margins\.[a-z]+: .+$', bar_window, re.M)),
                   'BAR_ZONE': binding('exclusiveZone', bar_window),
                   'OVERLAY_ANCHORS': anchors(overlay),
                   'OVERLAY_MODE': binding('exclusionMode', overlay),
                   'OVERLAY_ZONE': binding('exclusiveZone', overlay),
                   'OVERLAY_MARGINS': '\n'.join(re.findall(r'^ *margins\.[a-z]+: .+$', overlay.split('            FocusScope {')[0], re.M)),
                   'BAR_VISIBLE': re.search(r'readonly property bool barVisible: ([\s\S]*?)\n    readonly', native)[1],
                   'CONTENT_INSET': binding('anchors.topMargin', native[native.index('                id: input'):]),
                   'RESERVATION': binding('readonly property int reservation'),
                   'HOVER_PAGE': binding('readonly property string hoverPage'),
                   'POPOUT_X': binding('x', popout), 'POPOUT_Y': binding('y', popout),
                   'POPOUT_HEIGHT': binding('height', popout)}.items():
    qml = qml.replace('__' + key + '__', value)
# Production still makes its native request using the measured extent.
assert 'implicitHeight: root.barExtent' in bar_window
assert 'exclusiveZone: panel.reservation' in bar_window
for theme in ('tokyo-night', 'gruvbox-light'):
    with tempfile.TemporaryDirectory(prefix='icewine-bar-geometry-') as temporary:
        root = Path(temporary)
        (root / 'icewine').mkdir()
        (root / 'icewine/modules').symlink_to(source / 'quickshell/modules')
        shutil.copytree(source / 'quickshell/config', root / 'config')
        (root / 'icewine/theme').symlink_to(root / 'theme')
        config = theme_fixture(source, root, theme)
        (root / 'runtime').mkdir(mode=0o700)
        (root / 'shell.qml').write_text(qml)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                   QT_SCALE_FACTOR='1.5' if theme == 'gruvbox-light' else '1',
                   QML_IMPORT_PATH=str(root), XDG_CONFIG_HOME=config, XDG_STATE_HOME=str(root / 'state'),
                   XDG_CACHE_HOME=str(root / 'cache'), XDG_RUNTIME_DIR=str(root / 'runtime'),
                   ICEWINE_WIDGET_POLICY='{}', HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='',
                   DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(root / 'no-session-bus'),
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'no-system-bus'))
        result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                                capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if result.returncode or 'BAR_GEOMETRY_PASSED' not in output or re.search(r'(ReferenceError|TypeError|FAIL!|Cannot assign)', output):
            raise AssertionError(theme + '\n' + output)
if '--capture-only' in sys.argv:
    print('capture: actual bar surface already-closing slide/fade finish immediately; normal transitions, dark/light at 1x/1.5x pass')
else:
    print('bar geometry: real surface, corners, live native layer/focus and edge/reservation/available-area requests, captured output bounds, animated transitions, foreign zones, overflow dragging, live settings, handheld/radial, dark/light at 1x/1.5x pass')
