#!/usr/bin/env python3
"""Run the real switcher QML with synthetic native-object stand-ins and offscreen Qt.
Run: python3 tests/window-switcher.py . (qs on PATH).
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
qml = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules" as Modules
ShellRoot {
    id: shell
    QtObject {
        id: mockCompositor
        property var toplevels: [a, b, c]
        property string activeWindowAddress: "0x2"
    }
    QtObject { id: ws1; property int id: 1; property string name: "1"; property var monitor: ({name: "DP-1"}) }
    QtObject { id: ws3; property int id: 3; property string name: "3"; property var monitor: ({name: "DP-1"}) }
    QtObject { id: a; property string address: "0x1"; property string title: "First"; property var workspace: ws1; property var wayland: null }
    QtObject { id: b; property string address: "0x2"; property string title: "Selected"; property var workspace: ws1; property var wayland: null }
    QtObject { id: c; property string address: "0x3"; property string title: "Third"; property var workspace: ws3; property var wayland: null }
    QtObject { id: d; property string address: "0x4"; property string title: "Fourth"; property var workspace: ws1; property var wayland: null }
    Window {
        id: window
        width: 420; height: 280; visible: true
        property int activations: 0
        property int dismissals: 0
        property var activated: null
        Loader {
            id: loader
            anchors.fill: parent
            sourceComponent: Modules.WindowSwitcher {
                compositor: mockCompositor
                monitorName: "DP-1"
                onActivateRequested: selected => { ++window.activations; window.activated = selected }
                onDismissRequested: ++window.dismissals
            }
        }
        TestCase {
            id: keys
            when: false
            function descendants(item, predicate) {
                let result = predicate(item) ? [item] : []
                for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
                return result
            }
            function selectedCardVisible() {
                const card = descendants(loader.item, item => item.modelData === loader.item.selected
                    && item.border !== undefined)[0]
                if (!card) return false
                const position = card.mapToItem(loader.item, 0, 0)
                return position.x >= 16 && position.x + card.width <= loader.width - 15
                    && position.y >= 16 && position.y + card.height <= loader.height - 15
            }
            function check() {
                const view = loader.item
                view.forceActiveFocus()
                tryVerify(() => view.activeFocus)
                compare(view.selected, b)
                tryVerify(() => descendants(view, item => item.text === "Selected"
                    && item.wrapMode === Text.Wrap && item.visible).length > 0, 2000, "Unavailable preview has visible fallback")
                keyRelease(Qt.Key_Return)
                compare(window.activations, 0, "Opening release is inert")
                keyPress(Qt.Key_Return)
                keyClick(Qt.Key_Left)
                compare(view.selected, a)
                keyRelease(Qt.Key_Return)
                compare(window.activated, b, "Activate the pressed window despite selection changing")
                compare(window.activations, 1)
                view.selected = b
                keyPress(Qt.Key_Return)
                mockCompositor.toplevels = [a, c]
                tryCompare(view, "selected", a)
                keyRelease(Qt.Key_Return)
                compare(window.activations, 1, "Closed armed window is not replaced")
                keyPress(Qt.Key_Return)
                view.focus = false
                window.contentItem.forceActiveFocus()
                tryVerify(() => !view.activeFocus)
                view.forceActiveFocus()
                keyRelease(Qt.Key_Return)
                compare(window.activations, 1, "Focus loss cancels activation")
                keyClick(Qt.Key_Escape)
                compare(window.dismissals, 1)
                mockCompositor.toplevels = [a, b, d, c]
                tryVerify(() => view.rows[0].windows.length === 3)
                view.selected = a
                keyClick(Qt.Key_Right)
                keyClick(Qt.Key_Right)
                compare(view.selected, d)
                tryVerify(selectedCardVisible, 2000, "Selected card is visible after horizontal navigation")
                keyClick(Qt.Key_Down)
                compare(view.selected, c)
                tryVerify(selectedCardVisible, 2000, "Selected card is visible after workspace navigation")
                mockCompositor.toplevels = []
                tryVerify(() => view.rows.length === 0)
                keyClick(Qt.Key_Return)
                compare(window.activations, 1, "Empty switcher cannot activate a stale selection")
                console.log("SWITCHER_PASSED")
                Qt.quit()
            }
        }
        Timer {
            interval: 100; running: true
            onTriggered: {
                try { keys.check() }
                catch (error) { console.error("Switcher check failed:", error, error.stack); Qt.exit(1) }
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='.switcher-check-') as directory:
    root = Path(directory)
    (root / 'icewine').mkdir()
    (root / 'icewine/modules').symlink_to(source / 'quickshell/modules')
    (root / 'icewine/theme').symlink_to(root / 'theme')
    (root / 'config').symlink_to(source / 'quickshell/config')
    (root / 'theme').mkdir()
    palette = (source / 'theme/assets/templates/Palette.qml.in').read_text()
    (root / 'theme/Palette.qml').write_text(re.sub(r'@\w+@', '7aa2f7', palette))
    (root / 'theme/qmldir').write_text('singleton Palette 1.0 Palette.qml\n')
    (root / 'shell.qml').write_text(qml)
    (root / 'runtime').mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen',
               HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='',
               DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(root / 'no-session-bus'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'no-system-bus'),
               XDG_CACHE_HOME=str(root / 'cache'), XDG_RUNTIME_DIR=str(root / 'runtime'))
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'SWITCHER_PASSED' in output, output
    assert not re.search(r'ReferenceError|TypeError|Binding loop|Unable to assign|not a type', output), output
    print('Native switcher frozen-key/closure/focus cancellation, fallback and selected-card scrolling pass')
