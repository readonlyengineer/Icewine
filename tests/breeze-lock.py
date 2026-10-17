#!/usr/bin/env python3
"""Exercise the actual minimal clock lock surface and SessionControl's native InputPanel.
Requires Quickshell with Qt Quick Effects and Qt Virtual Keyboard. No compositor lock or PAM login is
attempted: the fixture owns auth outcomes; the existing lifecycle checks exercise
the real session handlers separately. This is not device validation.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from qml_fixture import theme_fixture

source = Path(sys.argv[1]).resolve()
qml = '''import QtQuick
import QtQuick.Window
import QtQuick.VirtualKeyboard
import QtTest
import Quickshell
import "icewine/modules" as Modules
import qs.icewine.theme as Theme
import "icewine/modules/Wallpaper.js" as Wallpaper
ShellRoot {
    id: root
    property string phase: "startup"
    readonly property Item view: viewLoader.item
    readonly property var fixtureSession: session
    QtObject {
        id: wallpaperOwner
        property bool selectionAvailable: true
        property string revision: "initial"
        property string dataHome: Quickshell.env("XDG_DATA_HOME")
        readonly property url sourceUrl: Wallpaper.source(dataHome, selectionAvailable, revision)
    }
    Modules.SessionControl { id: keyboardOwner; authenticationRequired: true }
    QtObject {
        id: session
        property var wallpaper: wallpaperOwner
        property bool locked: true
        property bool authenticationRequired: true
        property string password: ""
        property bool authenticating: false
        property bool failed: false
        property alias keyboardHost: keyboardOwner.keyboardHost
        property alias keyboardVisible: keyboardOwner.keyboardVisible
        property alias keyboardHeight: keyboardOwner.keyboardHeight
        property int submissions: 0
        function submit() {
            if (authenticating || (authenticationRequired && !password)) return
            ++submissions
            if (authenticationRequired) authenticating = true
            else locked = false
        }
        function complete(success) {
            password = ""
            failed = !success
            authenticating = false
            if (success) locked = false
        }
        function toggleKeyboard(host) { keyboardOwner.toggleKeyboard(host) }
    }
    Window {
        id: win
        visible: true; width: 1280; height: 800
        Loader {
            id: viewLoader
            anchors.fill: parent
            sourceComponent: Modules.LockScreenSurface { session: root.fixtureSession }
        }
        TestCase { id: keys; when: false }
    }
    Window {
        id: win2
        visible: false; width: 800; height: 600
        Loader {
            id: secondView
            anchors.fill: parent
            active: win2.visible
            sourceComponent: Modules.LockScreenSurface { session: root.fixtureSession }
        }
    }
    function find(item, predicate) {
        if (predicate(item)) return item
        for (const child of item.children ?? []) {
            const match = find(child, predicate)
            if (match) return match
        }
        return null
    }
    Timer {
        interval: 150; running: true
        onTriggered: {
            try {
                root.phase = "initial focus and theme"
                win.requestActivate()
                keys.tryCompare(win, "active", true)
                const field = view.passwordInput
                keys.tryCompare(field, "activeFocus", true)
                keys.compare(field.echoMode, TextInput.NoEcho)
                keys.compare(field.opacity, 0, "no secret or length display")
                const clock = find(view, item => item.objectName === "lockClock")
                const image = find(view, item => item.objectName === "lockWallpaper")
                keys.tryCompare(wallpaperOwner, "selectionAvailable", false)
                keys.tryCompare(image, "status", Image.Ready)
                keys.verify(String(image.source).includes("/wallpapers/default.jpg"), "missing selection uses existing resolver fallback")
                root.phase = "selected wallpaper refresh"
                wallpaperOwner.dataHome += "/selected"
                wallpaperOwner.selectionAvailable = true
                wallpaperOwner.revision = "selected-refresh"
                keys.tryCompare(image, "status", Image.Ready)
                keys.verify(String(image.source).includes("selection.img?revision=selected-refresh"))
                root.phase = "neutral focus, native edits and bounded feedback"
                field.focus = false
                view.forceActiveFocus()
                keys.keyClick(Qt.Key_A)
                keys.verify(field.activeFocus, "first printable key restores focus")
                keys.compare(field.text, "a", "first character arrives once")
                keys.compare(session.password, "a")
                keys.verify(String(clock.color) !== "#ffffff", "edit gives colour feedback")
                if (Theme.Palette.animate) {
                    keys.tryVerify(() => clock.scale > 1, 100, "clock pulse starts")
                    keys.verify(clock.scale <= 1.0251, "clock pulse is bounded")
                } else keys.compare(clock.scale, 1, "reduced motion changes colour only")
                keys.keyClick(Qt.Key_B)
                keys.wait(100)
                keys.verify(String(clock.color) !== "#ffffff", "rapid typing extends one feedback window")
                keys.wait(220)
                keys.fuzzyCompare(clock.scale, 1, 0.0001)
                keys.compare(String(clock.color), "#ffffff")
                keys.keyPress(Qt.Key_Shift); keys.keyRelease(Qt.Key_Shift)
                keys.compare(String(clock.color), "#ffffff", "navigation is not an edit")
                keys.keyClick(Qt.Key_Backspace)
                keys.compare(field.text, "a")
                keys.verify(String(clock.color) !== "#ffffff", "edit gives colour feedback")
                keys.keyClick(Qt.Key_Escape)
                keys.compare(field.text, "")
                keys.compare(session.password, "")
                keys.wait(320)
                keys.keyClick(Qt.Key_Backspace)
                keys.compare(String(clock.color), "#ffffff", "empty backspace does not pulse")
                keys.keyClick(Qt.Key_A)
                keys.keyClick(Qt.Key_U, Qt.ControlModifier)
                keys.compare(field.text, "", "Ctrl+U clears")
                keys.keyClick(Qt.Key_A)
                keys.keyClick(Qt.Key_Z, Qt.ControlModifier)
                keys.compare(field.text, "a", "undo cannot restore previous secrets")
                keys.keyClick(Qt.Key_C, Qt.ControlModifier)
                keys.compare(field.selectedText, "", "no selection or clipboard helper introduced")
                root.phase = "shared password across output surfaces"
                win2.visible = true
                keys.tryVerify(() => secondView.item !== null)
                const secondField = secondView.item.passwordInput
                keys.compare(secondField.text, "a")
                win2.requestActivate()
                keys.tryCompare(win2, "active", true)
                secondField.forceActiveFocus()
                keys.keyClick(Qt.Key_B)
                keys.compare(field.text, "ab")
                keys.compare(session.password, "ab")
                win.requestActivate()
                keys.tryCompare(win, "active", true)
                field.forceActiveFocus()
                root.phase = "Tab and native keyboard activation"
                keys.keyClick(Qt.Key_Tab)
                const footer = find(view, item => item.objectName === "lockKeyboard")
                keys.verify(footer.activeFocus, "Tab reaches keyboard control")
                keys.keyClick(Qt.Key_Tab, Qt.ShiftModifier)
                keys.verify(field.activeFocus, "Backtab returns to concealed input")
                keys.mouseClick(footer)
                keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                keys.verify(field.activeFocus, "keyboard activation focuses concealed input")
                keys.mouseClick(footer)
                keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                field.forceActiveFocus()
                root.phase = "submission and busy state"
                keys.keyClick(Qt.Key_Return)
                keys.verify(session.authenticating && session.locked, "submit retains lock")
                keys.compare(field.text, "", "visible password clears while PAM retains response")
                keys.compare(session.password, "ab", "pending PAM response preserved")
                keys.compare(secondField.text, "", "all output-local buffers clear while busy")
                keys.keyClick(Qt.Key_Return)
                keys.compare(session.submissions, 1, "no concurrent submission")
                keys.keyClick(Qt.Key_B)
                keys.compare(field.text, "", "busy input suppressed")
                keys.compare(session.submissions, 1)
                root.phase = "failed response retry"
                session.complete(false)
                keys.tryCompare(field, "activeFocus", true)
                keys.verify(session.locked && session.failed && !field.text, "failed retry preserves lock and clears secret")
                const toggle = find(view, item => item.text === "Virtual Keyboard")
                for (const size of [[1920,1080], [1280,800], [800,600], [320,480]]) {
                    root.phase = "native keyboard " + size.join("x")
                    win.width = size[0]; win.height = size[1]
                    keys.wait(100)
                    field.forceActiveFocus()
                    keys.mouseClick(toggle)
                    keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                    const panel = find(view, item => item.active !== undefined && item.externalLanguageSwitchEnabled !== undefined)
                    keys.verify(panel && panel.width <= Math.min(win.width, 900, win.height * 1.5)
                        && panel.height > 0 && panel.y + panel.height <= win.height, "native keyboard bounds")
                    keys.wait(250)
                    const mapped = field.mapToItem(view, 0, 0)
                    keys.verify(mapped.y >= 0 && mapped.y + field.height <= win.height - panel.height, "field above keyboard")
                    const letter = find(panel, item => item.keyType === QtVirtualKeyboard.KeyType.Key && item.text === "a")
                    const backspace = find(panel, item => item.key === Qt.Key_Backspace && item.keyType !== undefined)
                    keys.verify(letter && backspace, "native keys loaded")
                    field.text = "secret"
                    keys.mouseClick(letter)
                    keys.tryCompare(field, "text", "secreta")
                    keys.mouseClick(backspace)
                    keys.tryCompare(field, "text", "secret")
                    const before = field.text
                    root.phase = "live theme with keyboard " + size.join("x")
                    Theme.Palette.snapshot = JSON.parse(Quickshell.env("ICEWINE_LIGHT_PALETTE"))
                    keys.wait(250)
                    keys.compare(field.text, before, "theme change retains input")
                    keys.compare(String(clock.color), "#ffffff", "clock remains readable on dim wallpaper with light theme")
                    keys.verify(field.activeFocus, "theme change retains focus")
                    keys.mouseClick(toggle)
                    keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                    keys.tryCompare(field, "activeFocus", true)
                }
                root.phase = "successful response"
                field.forceActiveFocus()
                session.password = "correct-fixture-response"
                keys.keyClick(Qt.Key_Return)
                keys.compare(session.submissions, 2)
                session.complete(true)
                keys.verify(!session.locked && !session.password && !field.text, "success clears response")
                session.locked = true
                root.phase = "authentication-disabled policy"
                session.authenticationRequired = false
                view.forceActiveFocus()
                keys.keyClick(Qt.Key_Return)
                keys.verify(!session.locked, "authentication-required policy retained")
                session.locked = true
                keys.mouseClick(view, 100, 100)
                keys.verify(!session.locked, "disabled-auth touch path")
                root.phase = "opaque wallpaper failure"
                wallpaperOwner.dataHome += "/missing"
                wallpaperOwner.selectionAvailable = true
                wallpaperOwner.revision = "refresh"
                keys.tryCompare(wallpaperOwner, "selectionAvailable", false)
                keys.tryCompare(image, "status", Image.Error)
                keys.compare(find(view, item => item.objectName === "lockBackdrop").color.a, 1)
                root.phase = "native surface teardown"
                win2.visible = false
                // Release the surface while its native singleton services are alive,
                // as the compositor does on unlock, before QML engine shutdown.
                viewLoader.active = false
                keys.wait(20)
                console.log("CLOCK_LOCK_PASSED")
                Qt.quit()
            } catch (error) {
                console.error("CLOCK_LOCK_FAILED phase=" + root.phase + "\\n" + (error.stack || error))
                Qt.exit(1)
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    (root / "icewine/modules").symlink_to(source / "quickshell/modules")
    (root / "icewine/theme").symlink_to(root / "theme")
    config = theme_fixture(source, root)
    import runpy
    render = runpy.run_path(str(source / "scripts/theme"))
    assets = source / "theme/assets"
    light = render["render_theme"](assets, assets / "themes/gruvbox-light.json")["palette.json"]
    import shutil
    (root / "data/wallpapers").mkdir(parents=True)
    shutil.copyfile(source / "theme/assets/flower-branch.png", root / "data/wallpapers/default.jpg")
    (root / "data/selected/wallpapers").mkdir(parents=True)
    shutil.copyfile(source / "theme/assets/flower-branch.png", root / "data/selected/wallpapers/default.jpg")
    (root / "data/selected/icewine/wallpapers").mkdir(parents=True)
    shutil.copyfile(source / "theme/assets/flower-branch.png", root / "data/selected/icewine/wallpapers/selection.img")
    (root / "runtime").mkdir(mode=0o700)
    (root / "shell.qml").write_text(qml)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               QT_DEBUG_PLUGINS="1",
               QT_IM_MODULE="qtvirtualkeyboard", QT_VIRTUALKEYBOARD_DESKTOP_DISABLE="1",
               XDG_CONFIG_HOME=config, QML_IMPORT_PATH=str(root), XDG_DATA_HOME=str(root / "data"), XDG_CACHE_HOME=str(root / "cache"),
               XDG_RUNTIME_DIR=str(root / "runtime"), DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "no-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"), ICEWINE_LIGHT_PALETTE=light)
    result = subprocess.run([os.environ.get("ICEWINE_TEST_QS", "qs"), "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "CLOCK_LOCK_PASSED" in output, output
    assert re.search(r'libqtvirtualkeyboardplugin\.so[^\n]*loaded library', output), output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign|is not installed|not a type", output), output
print("PASS: actual clock lock surface, failure/retry/busy/clearing, policy, focus, native OSK, theme and small screens")
