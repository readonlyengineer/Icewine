#!/usr/bin/env python3
"""Exercise the actual Breeze lock adapter and SessionControl's native InputPanel.
Requires the packaged Quickshell/KDE runtime. No compositor lock or PAM login is
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
import org.kde.kirigami as Kirigami
import QtTest
import Quickshell
import "icewine/modules" as Modules
import qs.icewine.theme as Theme
ShellRoot {
    id: root
    property string phase: "startup"
    readonly property Item view: viewLoader.item
    readonly property var fixtureSession: session
    Modules.SessionControl { id: keyboardOwner; authenticationRequired: true }
    QtObject {
        id: session
        property bool locked: true
        property bool authenticationRequired: true
        property string password: ""
        property bool authenticating: false
        property bool failed: false
        property alias keyboardHost: keyboardOwner.keyboardHost
        property alias keyboardVisible: keyboardOwner.keyboardVisible
        property alias keyboardHeight: keyboardOwner.keyboardHeight
        property int submissions: 0
        property int reboots: 0
        property int shutdowns: 0
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
        function requestReboot() { ++reboots }
        function requestShutdown() { ++shutdowns }
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
                keys.compare(String(find(view, item => item.objectName === "lockBackdrop").color), "#000000")
                keys.compare(field.Kirigami.Theme.textColor, Theme.Palette.foreground)
                keys.compare(Qt.application.name, "quickshell", "KConfig application namespace")
                if (!Theme.Palette.animate) {
                    // The native Breeze plugin clamps longDuration to at least 1ms.
                    keys.compare(Kirigami.Units.veryShortDuration, 0)
                    keys.compare(Kirigami.Units.shortDuration, 0)
                    keys.compare(Kirigami.Units.longDuration, 1)
                    keys.compare(Kirigami.Units.veryLongDuration, 2)
                }
                root.phase = "neutral focus input"
                field.focus = false
                view.forceActiveFocus()
                keys.keyClick(Qt.Key_A)
                keys.verify(field.activeFocus, "first printable key restores focus")
                keys.compare(field.text, "a", "first character arrives once")
                for (const key of [Qt.Key_Return, Qt.Key_Enter]) {
                    field.focus = false
                    view.forceActiveFocus()
                    keys.keyClick(key)
                    keys.verify(field.activeFocus, "neutral Enter restores focus")
                    keys.compare(session.submissions, 0, "neutral Enter is focus only")
                    keys.compare(field.text, "a", "neutral Enter retains response")
                }
                field.focus = false
                view.forceActiveFocus()
                keys.keyClick(Qt.Key_A, Qt.ControlModifier)
                keys.verify(field.activeFocus, "modified key restores focus")
                keys.compare(field.selectedText, "a", "native select-all shortcut")
                field.text = ""
                field.focus = false
                view.forceActiveFocus()
                keys.keyPress(Qt.Key_Shift); keys.keyRelease(Qt.Key_Shift)
                keys.verify(field.activeFocus && !field.text && !session.submissions,
                    "modifier-only input focuses without text or submission")
                field.text = "a"
                keys.compare(session.password, "a")
                root.phase = "Tab and footer navigation"
                keys.keyClick(Qt.Key_Tab)
                keys.verify(find(view, item => item.objectName === "lockSubmit").activeFocus, "Tab reaches submit")
                keys.keyClick(Qt.Key_Tab, Qt.ShiftModifier)
                keys.verify(field.activeFocus, "Backtab returns to password")
                const footer = find(view, item => item.text === "Virtual Keyboard")
                footer.forceActiveFocus()
                keys.keyClick(Qt.Key_Left)
                keys.verify(!field.activeFocus, "footer navigation retains explicit focus")
                keys.keyClick(Qt.Key_Space)
                keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                keys.verify(field.activeFocus, "explicit keyboard activation focuses password")
                footer.forceActiveFocus()
                // Native input-method dismissal follows loss of text input focus.
                keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                keys.keyClick(Qt.Key_Space)
                keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                keys.verify(field.activeFocus, "keyboard activation restores input focus")
                keys.mouseClick(footer)
                keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                field.forceActiveFocus()
                root.phase = "submission and busy state"
                keys.keyClick(Qt.Key_Return)
                keys.verify(session.authenticating && session.locked, "submit retains lock")
                keys.compare(field.text, "", "visible password clears while PAM retains response")
                keys.compare(session.password, "a", "pending PAM response preserved")
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
                    keys.compare(String(find(view, item => item.objectName === "lockBackdrop").color), "#ffffff")
                    keys.compare(field.Kirigami.Theme.textColor, Theme.Palette.foreground)
                    keys.compare(field.Kirigami.Theme.highlightedTextColor, Theme.Palette.highlightedText)
                    keys.verify(field.activeFocus, "theme change retains focus")
                    keys.mouseClick(toggle)
                    keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                    keys.tryCompare(field, "activeFocus", true)
                }
                root.phase = "power callbacks and successful response"
                find(view, item => item.text === "Restart").click()
                find(view, item => item.text === "Shut Down").click()
                keys.compare(session.reboots, 1); keys.compare(session.shutdowns, 1)
                field.forceActiveFocus()
                field.text = "correct-fixture-response"
                keys.keyClick(Qt.Key_Return)
                keys.compare(session.submissions, 2)
                session.complete(true)
                keys.verify(!session.locked && !session.password && !field.text, "success clears response")
                session.locked = true
                root.phase = "authentication-disabled policy"
                session.authenticationRequired = false
                keys.mouseClick(find(view, item => item.objectName === "lockSubmit"))
                keys.verify(!session.locked, "authentication-required policy retained")
                root.phase = "native surface teardown"
                // Release the surface while its native singleton services are alive,
                // as the compositor does on unlock, before QML engine shutdown.
                viewLoader.active = false
                keys.wait(20)
                console.log("BREEZE_LOCK_PASSED")
                Qt.quit()
            } catch (error) {
                console.error("BREEZE_LOCK_FAILED phase=" + root.phase + "\\n" + (error.stack || error))
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
    (root / "runtime").mkdir(mode=0o700)
    (root / "shell.qml").write_text(qml)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               QT_IM_MODULE="qtvirtualkeyboard", QT_VIRTUALKEYBOARD_DESKTOP_DISABLE="1",
               XDG_CONFIG_HOME=config, QML_IMPORT_PATH=str(root), XDG_CACHE_HOME=str(root / "cache"),
               XDG_RUNTIME_DIR=str(root / "runtime"), DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "no-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"), ICEWINE_LIGHT_PALETTE=light)
    result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                            capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "BREEZE_LOCK_PASSED" in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign|is not installed|not a type", output), output
print("PASS: actual Breeze lock form, failure/retry/busy/clearing, policy, focus, native OSK, theme and small screens")
