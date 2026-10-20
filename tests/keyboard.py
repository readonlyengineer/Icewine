#!/usr/bin/env python3
"""Actual QS keyboard owner with a fake wtype child: ordering, failure and lock gate.
No compositor injection or PAM. Run with the installed qs on PATH.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from qml_fixture import theme_fixture

source = Path(sys.argv[1]).resolve()
qml = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import "icewine/modules" as Modules
import "owner" as Owner
import "icewine/modules/KeyboardModel.js" as Model
ShellRoot {
    id: root
    property string phase: "startup"
    property int deliveryStarts: 0
    property int deliveryExits: 0
    property int hides: 0
    Connections { target: owner; function onHiding() { root.hides++ } }
    property int lastExit: -1
    QtObject { id: first; property string address: "0x1" }
    QtObject { id: second; property string address: "0x2" }
    QtObject {
        id: compositor
        property string activeWindowAddress: first.address
        property var toplevels: [first, second]
        function monitorFor(screen) { return {focused: true} }
    }
    Modules.SessionControl { id: session; authenticationRequired: true; keyboardController: owner }
    Owner.KeyboardController { id: owner; compositor: compositor; session: session; fixtureHost: win.contentItem }
    Connections {
        target: owner.deliveryProcess
        function onStarted() { root.deliveryStarts++ }
        function onExited(code, status) { root.deliveryExits++; root.lastExit = code }
    }
    FileView { id: calls; path: Quickshell.env("TEST_KEYBOARD_CALLS"); blockAllReads: true; printErrors: false }
    FileView { id: control; path: Quickshell.env("TEST_KEYBOARD_CONTROL"); blockWrites: true }
    Window {
        id: win; visible: true; width: 1280; height: 800
        Modules.LockScreenSurface { id: lockView; anchors.fill: parent; session: session }
        TestCase { id: check; when: false }
    }
    function count() { calls.reload(); return calls.text().trim().split("\\n").filter(Boolean).length }
    function find(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children ?? []) {
            const match = find(child, name)
            if (match) return match
        }
        return null
    }
    function geometry(locked) {
        session.lockRequested = locked
        session.keyboardHost = lockView
        // Exercise the cap, normal desktop and overflow/scrolling ceilings.
        for (const [width, height] of [[2560,1440], [1280,800], [320,240]]) {
            root.phase = (locked ? "lock" : "desktop") + " geometry " + width + "x" + height
            win.width = width; win.height = height
            check.wait(30)
            owner.show()
            const panel = owner.view
            check.tryCompare(panel, "visible", true)
            check.verify(panel.width <= width-24 && panel.height <= height*0.55+0.01, "output fit")
            const pin = find(panel, "keyboardPin"), hide = find(panel, "keyboardHide")
            for (const control of [pin, hide]) {
                const point = control.mapToItem(panel, 0, 0)
                check.verify(point.x >= 0 && point.x+control.width <= panel.width, "header control fits")
                check.verify(point.y >= 0 && point.y+control.height <= panel.height, "header control height fits")
                check.compare(control.height, panel.keyHeight)
            }
            check.mouseClick(pin); check.verify(!panel.pinned)
            check.mouseDrag(panel, panel.width/2, panel.keyHeight/2, -70, -60)
            check.verify(panel.x >= 0 && panel.y >= 0 && panel.x+panel.width <= width+0.01
                && panel.y+panel.height <= height+0.01, "drag stays bounded")
            check.mouseClick(pin); check.verify(panel.pinned)
            check.compare(panel.x, (width-panel.width)/2)
            for (const key of [Model.keys[0], Model.keys.find(key => key.text === " "), Model.keys[Model.keys.length - 1]]) {
                panel.selected = key.index; panel.revealSelected()
                const button = find(panel, "oskKey"+key.index), viewport = button.parent.parent
                const point = button.mapToItem(viewport, 0, 0)
                const visibleWidth = Math.min(viewport.width, point.x+button.width) - Math.max(0, point.x)
                // A wide Space key can exceed a narrow viewport; its visible part remains tappable.
                check.verify(visibleWidth >= Math.min(button.width, viewport.width)-0.01
                    && point.y >= -0.01 && point.y+button.height <= viewport.height+0.01,
                    "selected key reachable: "+key.index)
                check.compare(button.height, panel.keyHeight)
            }
            panel.selected = 0
            panel.controller({action:"ui_right", pressed:true})
            panel.controller({action:"ui_right", pressed:false})
            check.compare(panel.selected, 1, "controller navigation survives scaling")
            const firstKey = find(panel, "oskKey0")
            panel.selected = 0
            firstKey.forceActiveFocus(); check.keyClick(Qt.Key_Right)
            check.compare(panel.selected, 1, "keyboard navigation survives scaling")
            check.mouseClick(hide); check.tryCompare(owner, "visible", false)
        }
        win.width = 1280; win.height = 800
        session.lockRequested = false
        check.wait(30)
    }
    function headerHide(locked) {
        session.lockRequested = locked
        session.keyboardHost = lockView
        for (const touch of [false, true]) {
            for (const mode of ["pinned", "unpinned", "dragged", "repinned"]) {
                root.phase = (locked ? "lock" : "desktop") + " Hide " + mode + (touch ? " touch" : " mouse")
                owner.show()
                check.tryCompare(owner, "visible", true)
                const panel = owner.view
                check.verify(panel.pinned, "reopening resets pin")
                const pin = find(panel, "keyboardPin"), hide = find(panel, "keyboardHide")
                const tap = item => {
                    if (touch) {
                        const sequence = check.touchEvent(win)
                        sequence.press(0, item, item.width/2, item.height/2).commit()
                        sequence.release(0, item, item.width/2, item.height/2).commit()
                    } else check.mouseClick(item)
                }
                if (mode !== "pinned") {
                    tap(pin)
                    check.verify(!panel.pinned, "pointer unpins")
                }
                if (mode === "dragged" || mode === "repinned") {
                    const oldX = panel.x, oldY = panel.y
                    if (touch) {
                        const sequence = check.touchEvent(win)
                        const point = panel.mapToItem(win.contentItem, panel.width/2, 20)
                        sequence.press(0, win.contentItem, point.x, point.y).commit()
                        sequence.move(0, win.contentItem, point.x-35, point.y-30).commit()
                        sequence.move(0, win.contentItem, point.x-70, point.y-60).commit()
                        sequence.release(0, win.contentItem, point.x-70, point.y-60).commit()
                    } else check.mouseDrag(panel, panel.width/2, 20, -70, -60)
                    check.verify(panel.x < oldX && panel.y < oldY, "real header drag moves view")
                }
                if (mode === "repinned") {
                    tap(pin)
                    check.verify(panel.pinned, "pointer repins")
                    check.compare(panel.x, (panel.parent.width-panel.width)/2)
                }
                if (!locked) panel.controller({action:"ui_left", pressed:true})
                panel.modifiers = Model.shift; panel.caps = true
                const key = Model.keys.find(key => key.text === "a").index
                panel.arm(key)
                if (locked) {
                    check.wait(520)
                    check.verify(panel.repeated, "real repeat timer is active before Hide")
                }
                const selected = panel.selected, before = count(), password = session.password, hides = root.hides
                tap(hide)
                check.tryCompare(owner, "visible", false, 500)
                check.compare(root.hides, hides+1, "Hide notifies controller release-drain consumer")
                check.compare(panel.armed, -1, "Hide cancels armed input")
                check.compare(panel.repeated, false, "Hide cancels active repeat")
                check.compare(panel.modifiers, 0); check.compare(panel.caps, false)
                check.compare(panel.heldDirection, "")
                panel.release(key)
                panel.controller({action:"ui_accept", pressed:false})
                check.wait(550)
                check.compare(panel.selected, selected, "Hide stops navigation timer")
                check.compare(count(), before, "Hide stops repeats and late release without injection")
                check.compare(session.password, password, "Hide/release preserves lock input")
                check.compare(compositor.activeWindowAddress, second.address, "Hide preserves desktop destination focus")
                check.verify(!session.keyboardEnabled, "lock input method disabled on Hide")
            }
        }
        session.lockRequested = false
    }
    Timer { interval: 200; running: true; onTriggered: {
        try {
            owner.show()
            const pin = find(owner.view, "keyboardPin"), hide = find(owner.view, "keyboardHide")
            pin.forceActiveFocus(); const pinned = owner.view.pinned
            check.keyClick(Qt.Key_Space); check.compare(owner.view.pinned, !pinned)
            hide.forceActiveFocus(); check.keyClick(Qt.Key_Space)
            check.tryCompare(owner, "visible", false)
            const action = Model.action(Model.keys.find(key => key.text === "a"), Model.control, false)
            const process = owner.deliveryProcess
            const productionCommand = Array.from(process.command)
            check.verify(!JSON.stringify(productionCommand).includes("U0061"), "original production argv contains no typed keysym")
            root.phase = "one child, no backlog"
            owner.show(); check.verify(owner.desktopVisible)
            owner.send(action); check.verify(owner.busy)
            check.compare(JSON.stringify(process.command), JSON.stringify(productionCommand), "real send keeps production argv constant before any fixture override")
            check.compare(owner.deliveryInput, Model.command(action).join(" ") + "\\n", "real send carries the original input payload over stdin")
            owner.send(action)
            check.tryVerify(() => count() === 1)
            compositor.activeWindowAddress = second.address
            check.verify(!owner.desktopVisible, "destination change hides keyboard")
            check.tryCompare(owner, "busy", false, 4000)
            check.compare(count(), 1, "busy/focus transitions never replay work")
            check.compare(root.deliveryStarts, 1); check.compare(root.deliveryExits, 1)
            root.phase = "real child overlap with lock input gate"
            owner.show(); owner.send(action)
            check.verify(owner.busy)
            session.lockRequested = true
            check.verify(session.locked && !lockView.passwordInput.enabled, "lock acquisition retained, editor gated")
            check.keyClick(Qt.Key_X)
            check.compare(session.password, "")
            owner.send(action)
            check.tryCompare(owner, "busy", false, 4000)
            check.tryCompare(lockView.passwordInput, "enabled", true)
            check.compare(session.password, "")
            check.compare(count(), 2)
            root.phase = "child failure is generic and has no retry/backlog"
            session.lockRequested = false
            control.setText("fail"); control.waitForJob()
            owner.show(); owner.send(action)
            check.tryCompare(owner, "busy", false, 4000)
            check.verify(owner.error !== "" && owner.desktopVisible, "failure remains visible")
            owner.send(action); check.wait(100); check.compare(count(), 3, "failed owner refuses further input")
            owner.hide(); control.setText("ok"); control.waitForJob()
            owner.show(); check.compare(owner.error, "", "fresh invocation permits retry")
            owner.hide()
            root.phase = "bounded child timeout"
            control.setText("hang"); control.waitForJob()
            owner.show(); owner.send(action)
            check.tryCompare(owner, "busy", false, 4000)
            check.verify(owner.error !== "", "timeout fails closed without queued retries")
            owner.hide()
            root.phase = "empty child PATH is shell exit127, not startup failure"
            root.deliveryStarts = 0; root.deliveryExits = 0
            process.environment = {PATH:Quickshell.env("TEST_KEYBOARD_EMPTY_PATH")}
            owner.show(); owner.send(action)
            check.tryCompare(owner, "busy", false, 1000)
            check.verify(owner.error !== "")
            check.compare(root.deliveryStarts, 1); check.compare(root.deliveryExits, 1)
            check.compare(root.lastExit, 127, "shell started but cannot find timeout in child PATH")
            owner.hide(); process.environment = ({})
            root.phase = "failed startup releases pending and lock editor gate"
            root.deliveryStarts = 0; root.deliveryExits = 0
            const missingCommand = [Quickshell.env("TEST_KEYBOARD_MISSING_EXECUTABLE")].concat(productionCommand.slice(1))
            process.command = missingCommand
            owner.show(); owner.send(action)
            check.compare(JSON.stringify(process.command), JSON.stringify(missingCommand), "override changes only the executable, not original constant arguments")
            check.compare(owner.deliveryInput, Model.command(action).join(" ") + "\\n", "forced launch still receives the actual production payload")
            session.lockRequested = true
            check.verify(!lockView.passwordInput.enabled, "startup attempt gates lock editor")
            check.tryCompare(owner, "busy", false, 1000)
            check.verify(owner.error !== "" && owner.deliveryInput === "", "failed startup is terminal and discards input")
            check.compare(root.deliveryStarts, 0, "THIS delivery Process never started")
            check.compare(root.deliveryExits, 0, "FailedToStart emits no exited, unlike shell exit127")
            check.tryCompare(lockView.passwordInput, "enabled", true)
            check.compare(session.password, "")
            owner.send(action); check.wait(100); check.compare(count(), 4, "failed startup never queues a retry")
            session.lockRequested = false
            owner.hide(); process.command = productionCommand
            control.setText("ok"); control.waitForJob()
            owner.show(); check.compare(owner.error, "")
            owner.send(action)
            check.tryCompare(owner, "busy", false, 4000)
            check.compare(count(), 5, "fresh invocation recovers after failed startup")
            owner.hide()
            geometry(false); geometry(true)
            headerHide(false); headerHide(true)
            console.log("KEYBOARD_OWNER_PASSED"); Qt.quit()
        } catch (error) { console.error("KEYBOARD_OWNER_FAILED phase="+root.phase, error.stack || error); Qt.exit(1) }
    }}
}
'''
with tempfile.TemporaryDirectory(prefix="icewine-keyboard-") as directory:
    root = Path(directory)
    (root / "icewine").mkdir()
    (root / "icewine/modules").symlink_to(source / "quickshell/modules")
    (root / "icewine/theme").symlink_to(root / "theme")
    config = theme_fixture(source, root, os.environ.get("TEST_KEYBOARD_THEME", "tokyo-night"))
    # Offscreen has no layer-shell PanelWindow backend. Substitute only that
    # platform surface, keeping every owner handler/Process/Timer unchanged.
    # A fixture-only alias exposes the real Process for native signal counting
    # and a unique missing absolute executable; no production switch/fake error.
    (root / "owner").mkdir()
    for name in ("KeyboardView.qml", "KeyboardModel.js"):
        (root / "owner" / name).symlink_to(source / "quickshell/modules" / name)
    owner = (source / "quickshell/modules/KeyboardController.qml").read_text()
    owner = owner.replace("    id: root\n", "    id: root\n    property alias deliveryProcess: delivery\n    property Item fixtureHost\n", 1)
    start = owner.index("    PanelWindow {")
    end = owner.index("        KeyboardView {", start)
    owner = owner[:start] + "    Item { parent: root.fixtureHost; width: root.fixtureHost.width; height: root.fixtureHost.height; visible: root.desktopVisible && !root.session.locked\n" + owner[end:]
    (root / "owner/KeyboardController.qml").write_text(owner)
    (root / "bin").mkdir()
    (root / "empty-path").mkdir()
    missing_executable = root / "missing-delivery-executable"
    assert missing_executable.is_absolute() and not missing_executable.exists()
    (root / "runtime").mkdir(mode=0o700)
    (root / "control").write_text("ok")
    (root / "calls").write_text("")
    fake = root / "bin/wtype"
    fake.write_text("#!"+sys.executable+"\n"+'''import json, os, pathlib, sys, time
with open(os.environ["TEST_KEYBOARD_CALLS"], "a") as output:
    output.write(json.dumps(sys.argv[1:])+"\\n")
time.sleep(6 if pathlib.Path(os.environ["TEST_KEYBOARD_CONTROL"]).read_text() == "hang" else 0.18)
sys.exit(1 if pathlib.Path(os.environ["TEST_KEYBOARD_CONTROL"]).read_text() == "fail" else 0)
''')
    fake.chmod(0o755)
    (root / "shell.qml").write_text(qml)
    env = dict(os.environ, PATH=str(root / "bin")+":"+os.environ["PATH"], QT_QPA_PLATFORM="offscreen",
               QT_QUICK_BACKEND="software", QT_IM_MODULE="qtvirtualkeyboard", QT_VIRTUALKEYBOARD_DESKTOP_DISABLE="1",
               XDG_CONFIG_HOME=config, QML_IMPORT_PATH=str(root), XDG_DATA_HOME=str(root / "data"),
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
               DBUS_SESSION_BUS_ADDRESS="unix:path="+str(root / "no-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path="+str(root / "no-system-bus"),
               TEST_KEYBOARD_CALLS=str(root / "calls"), TEST_KEYBOARD_CONTROL=str(root / "control"), TEST_KEYBOARD_EMPTY_PATH=str(root / "empty-path"), TEST_KEYBOARD_MISSING_EXECUTABLE=str(missing_executable))
    result = subprocess.run([os.environ.get("ICEWINE_TEST_QS", "qs"), "-p", str(root), "--no-color"], env=env, capture_output=True, text=True, timeout=45)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and "KEYBOARD_OWNER_PASSED" in output, output
    startup_warnings = [line for line in output.splitlines()
                        if "Process failed to start" in line and str(missing_executable) in line]
    assert len(startup_warnings) == 1, output
    assert "U0061" not in output, "QS startup diagnostics must not include typed input"
    # This synthetic input is logged only by the explicit fake developer backend.
    commands = [json.loads(line) for line in (root / "calls").read_text().splitlines()]
    assert commands == [["-M", "ctrl", "-k", "U0061", "-m", "ctrl"]] * 5, commands
print("PASS: real delivery FailedToStart (0 started/0 exited) versus shell exit127 (1/1), constant production argv/stdin privacy, lock/busy/reopen/no-backlog exact fake-wtype argv, desktop/lock bounded geometry/edge and wide-key reachability/controller and keyboard navigation, mouse/touch Hide pinned/unpinned/drag/repin/reopen and input cancellation")
