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
import "icewine/modules/KeyboardModel.js" as KeyboardModel
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
    QtObject { id: external; property bool busy: false }
    Modules.SessionControl { id: keyboardOwner; authenticationRequired: true; lockRequested: true; keyboardController: external }
    QtObject {
        id: session
        property var wallpaper: wallpaperOwner
        property bool locked: true
        property alias authenticationRequired: keyboardOwner.authenticationRequired
        property string password: ""
        property alias authenticating: keyboardOwner.authenticating
        property bool failed: false
        property alias keyboardHost: keyboardOwner.keyboardHost
        property alias keyboardVisible: keyboardOwner.keyboardVisible
        readonly property bool externalKeyboardBusy: keyboardOwner.externalKeyboardBusy
        readonly property var keyboardView: keyboardOwner.keyboardView
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
                const prompt = find(view, item => item.objectName === "lockStatus")
                const toggle = find(view, item => item.objectName === "lockKeyboard")
                keys.verify(toggle.visible && toggle.enabled, "OSK prompt available before any submission")
                keys.compare(prompt.text, "", "no idle password or OSK instruction")
                keys.compare(toggle.text, "󰌌", "keyboard icon only")
                keys.compare(toggle.Accessible.name, "Toggle virtual keyboard")
                keys.compare(toggle.width, 44)
                keys.compare(toggle.height, 44)
                keys.compare(toggle.font.pixelSize, 24)
                const clock = find(view, item => item.objectName === "lockClock")
                function luminance(rgb) {
                    return rgb.map(v => v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))
                        .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
                }
                function checkTheme() {
                    const scrim = find(view, item => item.objectName === "lockScrim").color
                    const foreground = Theme.Palette.foreground
                    const a = luminance([foreground.r, foreground.g, foreground.b])
                    for (const wallpaper of [0, 1]) {
                        const b = luminance([scrim.r, scrim.g, scrim.b].map(v => v * scrim.a + wallpaper * (1 - scrim.a)))
                        keys.verify((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) >= 4.5,
                            "text contrast over black/white wallpaper extremes")
                    }
                    for (const name of ["lockClock", "lockDate", "lockStatus", "lockKeyboard"]) {
                        const item = find(view, item => item.objectName === name)
                        keys.compare(item.font.family, "JetBrainsMono Nerd Font", name + " shared font")
                        keys.compare(name === "lockKeyboard" ? item.palette.buttonText : item.color,
                            Theme.Palette.foreground, name + " live foreground")
                    }
                }
                checkTheme()
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
                keys.compare(prompt.text, "", "entry adds no OSK instruction")
                keys.verify(clock.color !== Theme.Palette.foreground, "edit gives colour feedback")
                if (Theme.Palette.animate) {
                    keys.tryVerify(() => clock.scale > 1, 100, "clock pulse starts")
                    keys.verify(clock.scale <= 1.0251, "clock pulse is bounded")
                } else keys.compare(clock.scale, 1, "reduced motion changes colour only")
                keys.keyClick(Qt.Key_B)
                keys.wait(100)
                keys.verify(clock.color !== Theme.Palette.foreground, "rapid typing extends one feedback window")
                keys.wait(220)
                keys.fuzzyCompare(clock.scale, 1, 0.0001)
                keys.compare(clock.color, Theme.Palette.foreground)
                keys.keyPress(Qt.Key_Shift); keys.keyRelease(Qt.Key_Shift)
                keys.compare(clock.color, Theme.Palette.foreground, "navigation is not an edit")
                keys.keyClick(Qt.Key_Backspace)
                keys.compare(field.text, "a")
                keys.verify(clock.color !== Theme.Palette.foreground, "edit gives colour feedback")
                keys.keyClick(Qt.Key_Escape)
                keys.compare(field.text, "")
                keys.compare(session.password, "")
                keys.wait(320)
                keys.keyClick(Qt.Key_Backspace)
                keys.compare(clock.color, Theme.Palette.foreground, "empty backspace does not pulse")
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
                root.phase = "external chord crossing lock acquisition"
                external.busy = true
                keys.verify(!field.enabled, "password disabled until external chord settles")
                keys.verify(toggle.visible && !toggle.enabled, "external input keeps OSK prompt visible and disabled")
                keys.keyClick(Qt.Key_X)
                keys.compare(session.password, "ab", "external input cannot edit lock response")
                external.busy = false
                keys.tryCompare(field, "activeFocus", true)
                root.phase = "Tab and native keyboard activation"
                keys.keyClick(Qt.Key_Tab)
                const footer = find(view, item => item.objectName === "lockKeyboard")
                keys.verify(footer.activeFocus, "Tab reaches keyboard control")
                keys.keyClick(Qt.Key_Tab, Qt.ShiftModifier)
                keys.verify(field.activeFocus, "Backtab returns to concealed input")
                keys.touchEvent(footer).press(0, footer, footer.width/2, footer.height/2).commit()
                keys.touchEvent(footer).release(0, footer, footer.width/2, footer.height/2).commit()
                keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                keys.verify(field.activeFocus, "keyboard activation focuses concealed input")
                keys.mouseClick(footer)
                keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                field.forceActiveFocus()
                root.phase = "submission and busy state"
                keys.keyClick(Qt.Key_Return)
                keys.verify(session.authenticating && session.locked, "submit retains lock")
                keys.verify(toggle.visible && !toggle.enabled, "busy authentication keeps OSK prompt visible and disabled")
                keys.compare(prompt.text, "Authenticating…")
                keys.verify(!keyboardOwner.keyboardView.enabled, "shared keyboard input disabled while PAM is busy")
                keyboardOwner.toggleKeyboard(view)
                keys.verify(!keyboardOwner.keyboardVisible, "programmatic toggle cannot open OSK while busy")
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
                keys.verify(toggle.visible && toggle.enabled, "failed retry restores OSK control")
                keys.compare(prompt.text, "Incorrect password")
                for (const size of [[1920,1080], [1280,800], [800,600], [320,480]]) {
                    checkTheme()
                    root.phase = "shared keyboard " + size.join("x")
                    win.width = size[0]; win.height = size[1]
                    keys.wait(100)
                    keys.verify(toggle.visible && toggle.x === 12
                        && toggle.y + toggle.height === view.height - 12,
                        "compact icon at bottom left before opening OSK")
                    field.forceActiveFocus()
                    keys.mouseClick(toggle)
                    keys.tryCompare(keyboardOwner, "keyboardVisible", true, 2000)
                    const panel = find(view, item => item.objectName === "sharedKeyboard")
                    keys.verify(panel && panel.width <= Math.min(1040, win.width - 24)
                        && panel.height > 0 && panel.y + panel.height <= win.height, "shared keyboard bounds")
                    keys.wait(250)
                    keys.verify(toggle.x === 12 && toggle.y >= 0
                        && toggle.y + toggle.height <= panel.y,
                        "bottom-left icon remains reachable above shared OSK")
                    const mapped = field.mapToItem(view, 0, 0)
                    keys.verify(mapped.y >= 0 && mapped.y + field.height <= win.height - panel.height, "field above keyboard")
                    const letter = find(panel, item => item.objectName === "oskKey" + KeyboardModel.keys.find(key => key.text === "a").index)
                    const backspace = find(panel, item => item.objectName === "oskKey" + KeyboardModel.keys.find(key => key.symbol === "BackSpace").index)
                    keys.verify(letter && backspace, "shared keys loaded")
                    field.text = "secret"
                    panel.selected = KeyboardModel.keys.find(key => key.text === "a").index
                    panel.move("left"); panel.move("right")
                    keys.mouseClick(letter)
                    keys.tryCompare(field, "text", "secreta")
                    panel.selected = KeyboardModel.keys.find(key => key.symbol === "BackSpace").index
                    panel.move("left"); panel.move("right")
                    keys.mouseClick(backspace)
                    keys.tryCompare(field, "text", "secret")
                    const before = field.text
                    keys.compare(KeyboardModel.keys.length, 84)
                    keys.compare(KeyboardModel.keys.filter(key => find(panel, item => item.objectName === "oskKey" + key.index)).length, 84, "all 84 keys rendered")
                    if (size[0] === 1280) {
                        field.forceActiveFocus()
                        keys.keyClick(Qt.Key_Tab); keys.keyClick(Qt.Key_Tab)
                        const accessiblePin = find(panel, item => item.objectName === "keyboardPin")
                        keys.verify(accessiblePin.activeFocus, "Tab reaches the visible pin control")
                        keys.keyClick(Qt.Key_Space); keys.verify(!panel.pinned, "keyboard can unpin")
                        keys.keyClick(Qt.Key_Space); keys.verify(panel.pinned, "keyboard can repin")
                        field.forceActiveFocus()
                        const a = KeyboardModel.keys.find(key => key.text === "a").index
                        const shift = KeyboardModel.keys.find(key => key.modifier === KeyboardModel.shift).index
                        const caps = KeyboardModel.keys.find(key => key.caps).index
                        panel.arm(shift); panel.release(shift)
                        keys.compare(panel.modifiers, KeyboardModel.shift, "shift is a UI latch")
                        panel.arm(a); panel.release(a)
                        keys.compare(field.text, before + "A", "Shift legend/action agree")
                        keys.compare(panel.modifiers, 0, "one-shot modifier clears")
                        panel.arm(caps); panel.release(caps)
                        panel.arm(shift); panel.release(shift)
                        panel.arm(a); panel.release(a)
                        keys.compare(field.text, before + "Aa", "Shift XOR Caps")
                        panel.cancel()
                        field.text = before
                        // Actual pointer cancellation and timer repeat exercise the shared view.
                        for (const touch of [false, true]) {
                            const sequence = touch ? keys.touchEvent(letter) : null
                            const press = () => touch ? sequence.press(0, letter, letter.width/2, 22).commit() : keys.mousePress(letter)
                            const leave = () => touch ? sequence.move(0, letter, -10, -10).commit() : keys.mouseMove(letter, -10, -10)
                            const release = (outside) => touch ? sequence.release(0, letter, outside ? -10 : letter.width/2, outside ? -10 : 22).commit() : keys.mouseRelease(letter, outside ? -10 : letter.width/2, outside ? -10 : 22)
                            root.phase = (touch ? "touch" : "pointer") + " exit before repeat"
                            press(); leave(); keys.wait(600)
                            keys.compare(field.text, before, "held outside before delay does not type")
                            keys.compare(panel.armed, -1, "exit cancels arm immediately")
                            release(true)
                            root.phase = (touch ? "touch" : "pointer") + " exit during repeat"
                            press(); keys.wait(560)
                            keys.verify(field.text.length > before.length, "inside hold repeats")
                            leave(); const atLeave = field.text; keys.wait(220)
                            keys.compare(field.text, atLeave, "exit stops future repeat")
                            release(true); keys.compare(field.text, atLeave, "outside release adds no click")
                            field.text = before
                            press(); release(false)
                            keys.compare(field.text, before + "a", "inside release commits once")
                            field.text = before
                        }
                        panel.selected = a
                        panel.controller({action:"ui_accept", pressed:true})
                        keys.wait(560)
                        panel.controller({action:"ui_accept", pressed:false})
                        keys.verify(field.text.length > before.length, "controller hold schedules finite repeats")
                        const afterRepeat = field.text
                        keys.wait(120)
                        keys.compare(field.text, afterRepeat, "release stops future repeat without duplicate click")
                        field.text = before
                        Theme.Palette.snapshot = Object.assign({}, Theme.Palette.snapshot, {keyboardOpacity:0.4})
                        keys.fuzzyCompare(panel.color.a, 0.4, 0.01, "live transparency")
                    }
                    panel.arm(KeyboardModel.keys.find(key => key.text === "a").index)
                    panel.cancelGesture()
                    panel.release(KeyboardModel.keys.find(key => key.text === "a").index)
                    keys.compare(field.text, before, "cancelled gesture does not type")
                    const pin = find(panel, item => item.objectName === "keyboardPin")
                    keys.mouseClick(pin)
                    keys.verify(!panel.pinned, "accessible pin toggle")
                    if (size[0] === 1280) {
                        const oldX = panel.x, oldY = panel.y
                        keys.mouseDrag(panel, panel.width/2, 20, -70, -60)
                        keys.verify(panel.x < oldX && panel.y < oldY, "unpinned header drag moves the keyboard")
                    }
                    panel.x = -100; panel.y = -100; panel.place()
                    keys.verify(panel.x >= 0 && panel.y >= 0, "unpinned position clamped")
                    keys.mouseClick(pin)
                    keys.verify(panel.pinned && panel.x === (win.width-panel.width)/2, "repin restores standard placement")
                    if (size[0] === 320) {
                        root.phase = "small-screen selection visibility"
                        function visibleSelection() {
                            const selectedKey = find(panel, item => item.objectName === "oskKey" + panel.selected)
                            const pos = selectedKey.mapToItem(panel, 0, 0)
                            return pos.x >= 7 && pos.y >= 47
                                && pos.x + selectedKey.width <= panel.width - 7
                                && pos.y + selectedKey.height <= panel.height - 7
                        }
                        panel.selected = 83
                        keys.tryVerify(visibleSelection)
                        keyboardOwner.toggleKeyboard(view); keyboardOwner.toggleKeyboard(view)
                        keys.compare(panel.selected, 0)
                        keys.tryVerify(visibleSelection, 2000, "reopen reveals reset selection")
                        panel.selected = 83
                        win.width = 280; win.height = 400
                        keys.tryVerify(visibleSelection, 2000, "geometry change preserves visible selection")
                        win.width = size[0]; win.height = size[1]
                        keys.tryVerify(visibleSelection)
                    }
                    root.phase = "live theme with keyboard " + size.join("x")
                    Theme.Palette.snapshot = JSON.parse(Quickshell.env("ICEWINE_LIGHT_PALETTE"))
                    keys.wait(250)
                    checkTheme()
                    keys.wait(250)
                    keys.compare(field.text, before, "theme change retains input")
                    keys.compare(clock.color, Theme.Palette.foreground, "clock follows live light theme")
                    keys.verify(field.activeFocus, "theme change retains focus")
                    keys.mouseClick(toggle)
                    keys.tryCompare(keyboardOwner, "keyboardVisible", false)
                    keys.tryCompare(field, "activeFocus", true)
                }
                root.phase = "successful response"
                field.forceActiveFocus()
                session.password = "correct-fixture-response"
                keyboardOwner.toggleKeyboard(view)
                const enter = KeyboardModel.keys.find(key => key.symbol === "Return").index
                keyboardOwner.keyboardView.arm(enter); keyboardOwner.keyboardView.release(enter)
                keys.compare(session.submissions, 2, "shared keyboard Enter delegates to guarded submit")
                session.complete(true)
                keys.verify(!session.locked && !session.password && !field.text, "success clears response")
                session.locked = true
                root.phase = "authentication-disabled policy"
                session.authenticationRequired = false
                keys.verify(toggle.visible && !toggle.enabled, "no-password policy retains prompt without opening a hidden editor")
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
print("PASS: actual clock lock surface, failure/retry/busy/clearing, policy, focus, shared 84-key OSK, arm/cancel/repeat/modifiers/pin/transparency and small screens")
