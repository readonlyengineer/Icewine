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
# panels cannot run offscreen; their request bindings are exercised on QtObjects.
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
    r'    readonly property (?:int|bool) (?:barHeight|barGap|barExtent|fullBar|floatingBar|bottomBar):', line))
def binding(name, text=native):
    match = re.search(r'^ *' + re.escape(name) + r': (.+)$', text, re.M)
    value = match[1]
    for line in text[match.end():].splitlines()[1:]:
        if value.count('(') == value.count(')'): break
        value += '\n' + line
    return value
popout = native.split('id: statusPopout')[1]
qml = '''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Effects
import QtTest
import Quickshell
import qs.config as Config
import "icewine/modules/topbar" as Bar
import "icewine/theme" as Theme
ShellRoot {
    id: root
    property bool fullWidth: false
    property bool radialVisible: false
    property bool barVisible: true
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
            __SURFACE__
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
        Timer {
            interval: 100; running: true
            onTriggered: {
                try { checks.test_geometry() }
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
            function test_geometry() {
                wait(100) // Let the real Settings FileView finish its initial read.
                for (const size of [[1280, 800], [640, 480], [853, 600]]) {
                    panel.width = size[0]; panel.height = size[1]
                    for (const behaviour of ["keyboard", "keyboard-mouse", "toggle", "always"])
                    for (const location of ["above", "top", "bottom"])
                    for (const style of ["anchored", "floating"])
                    for (const percent of [50, 99, 100]) {
                        Config.Settings.widgetSelections = {barBehaviour: behaviour, barLocation: location,
                            barWidth: percent, barStyle: style}
                        root.barVisible = true
                        wait(1)
                        const gap = style === "floating" ? 4 : 0
                        fuzzy(surface.width, panel.width * percent / 100, 0.001)
                        fuzzy(surface.x, (panel.width - surface.width) / 2, 0.001, "Exact logical output centring")
                        compare(surface.y, location === "bottom" ? panel.height - 38 - gap : gap)
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
                        root.barVisible = false
                        wait(1)
                        compare(panel.reservation, 0)
                        verify(surface.y + surface.height <= 0 || surface.y >= panel.height)
                    }
                }
                // Media-leading stacks use the retained independent capsule and routing.
                panel.width = 1280
                Config.Settings.widgetSelections = {barWidth: 100}
                root.barVisible = true
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
                panel.width = 640; root.barVisible = true
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
for key, value in {'PROPERTIES': properties, 'SURFACE': surface,
                   'RESERVATION': binding('readonly property int reservation'),
                   'HOVER_PAGE': binding('readonly property string hoverPage'),
                   'POPOUT_X': binding('x', popout), 'POPOUT_Y': binding('y', popout),
                   'POPOUT_HEIGHT': binding('height', popout)}.items():
    qml = qml.replace('__' + key + '__', value)
# Production still makes its native request using the measured extent.
assert 'implicitHeight: root.barExtent' in block('            property PanelWindow workArea: PanelWindow')
assert 'exclusiveZone: panel.reservation' in block('            property PanelWindow workArea: PanelWindow')
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
print('bar geometry: real surface, corners, gap/reservation requests, overflow dragging, live settings, handheld/radial, dark/light at 1x/1.5x pass')
