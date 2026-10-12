#!/usr/bin/env python3
"""Exercise Steam launch and real authentication adapters with offscreen mocks.
Run: python3 tests/render-ready.py . [preview-directory] [--native-osk=lock|sddm] [--workspaces=THEME].
Requires qs on PATH; native modes exercise one real InputPanel per process.
Workspace mode uses actual topbar QML and synthetic icons.
"""
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

workspace_theme = next((arg.split("=", 1)[1] for arg in sys.argv[2:]
                        if arg.startswith("--workspaces=")), None)
source = Path(sys.argv[1]).resolve()
native_adapter = next((arg.split("=", 1)[1] for arg in sys.argv[2:] if arg.startswith("--native-osk=")), None)
assert native_adapter in (None, "lock", "sddm")
preview_arg = next((arg for arg in sys.argv[2:] if not arg.startswith("--")), None)
preview_dir = Path(preview_arg).resolve() if preview_arg else None
if preview_dir:
    preview_dir.mkdir(parents=True, exist_ok=True)
qml = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import "icewine/modules" as Modules
import "sddm" as Sddm
import "theme" as Theme
ShellRoot {
    id: root
    property int launches: 0
    property var authChildren: []
    QtObject {
        id: compositor
        property var toplevels: []
        property string activated: ""
        signal monitorsChanged()
        function getMonitors() {
            return [{name: Quickshell.screens[0].name,
                width: 640, height: 480, focused: true}]
        }
        function activateWindow(address) { activated = address }
    }
    Modules.GameLauncher { id: launcher; compositor: compositor }
    Process {
        id: resetOverride
        command: ["rm", "--", Quickshell.env("XDG_DATA_HOME") + "/icewine/wallpapers/auth.img"]
    }
    Process {
        id: selectDesktop
        command: ["ln", "-s", Quickshell.env("XDG_DATA_HOME") + "/wallpapers/default.jpg",
            Quickshell.env("XDG_DATA_HOME") + "/icewine/wallpapers/selection.img"]
    }
    ListModel {
        id: userModel
        property int lastIndex: 0
        ListElement { name: "demo"; realName: "Peter" }
        ListElement { name: "guest"; realName: "" }
    }
    ListModel {
        id: sessionModel
        property int lastIndex: 1
        ListElement { name: "Other" }
        ListElement { name: "Hyprland" }
    }
    QtObject {
        id: sddm
        readonly property bool canReboot: true
        readonly property bool canPowerOff: true
        property int logins: 0
        signal loginFailed()
        signal loginSucceeded()
        function login(user, password, session) {
            if (user !== "guest" || password !== "test-secret" || session !== 0)
                throw new Error("Wrong SDDM login arguments")
            logins++
        }
    }
    Window {
        id: loginWindow
        visible: true
        width: 1920; height: 1080
        Sddm.Main { id: login; anchors.fill: parent; wallpaperSource: Qt.resolvedUrl("public-auth.img") }
        TestCase { id: keys; when: false }
    }
    property var auth: Array.from(login.children).find(child => child.controller !== undefined)
    Modules.SessionControl { id: session; authenticationRequired: false }
    QtObject {
        id: lockSession
        property bool locked: true
        property string wallpaperRevision: "initial"
        property string password: ""
        property bool authenticationRequired: true
        property bool authenticating: false
        property bool failed: false
        property var keyboardHost: null
        property bool keyboardVisible: false
        property real keyboardHeight: 280
        property int submissions: 0
        property int reboots: 0
        property int shutdowns: 0
        function submit() { ++submissions; authenticating = true; password = "" }
        function requestReboot() { ++reboots }
        function requestShutdown() { ++shutdowns }
        function toggleKeyboard(host) { keyboardHost = host; keyboardVisible = !keyboardVisible }
    }
    Window {
        id: lockWindow
        visible: true
        width: 1280; height: 800
        Modules.LockScreenSurface { id: locker; anchors.fill: parent; session: lockSession }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: lockSession.keyboardHeight
            visible: lockSession.keyboardVisible
            color: lockScreen.palette.backgroundDark
            border.color: lockScreen.palette.border
            Text { anchors.centerIn: parent; text: "Mock on-screen keyboard"; color: lockScreen.palette.foreground }
        }
    }
    property var lockScreen: Array.from(locker.children).find(child => child.controller !== undefined)
    function findItem(parent, name) {
        if (parent.objectName === name || parent.Accessible.name === name) return parent
        for (const child of parent.children ?? []) {
            const found = findItem(child, name)
            if (found) return found
        }
        return null
    }
    function checkLayout(screen, inset) {
        const panel = findItem(screen, "authPanel")
        const body = findItem(screen, "authBody")
        const footer = findItem(screen, "authFooter")
        const field = findItem(screen, "authPassword")
        const form = findItem(screen, "authForm")
        if (screen.height >= 800 && inset === 0
                && Math.abs(form.mapToItem(screen, 0, 0).y + form.height / 2 - screen.height / 2) > 1)
            throw new Error("Login details must be vertically centred")
        if (panel.width > screen.width || panel.height !== screen.height
                || panel.width < Math.min(screen.width, 288)
                || body.height <= 0 || footer.y + footer.height > screen.height - inset)
            throw new Error("Authentication panel/content bounds failed")
        const mapped = field.mapToItem(body, 0, 0)
        if (field.activeFocus && (mapped.y < -1 || mapped.y + field.height > body.height + 1))
            throw new Error("Focused password obscured by keyboard")
        const status = findItem(screen, "authStatus")
        const statusPosition = status.mapToItem(body, 0, 0)
        if (field.activeFocus && status.text && statusPosition.y + status.height > body.height + 1)
            throw new Error("Authentication status obscured by keyboard")
        const keyboardButton = findItem(screen, "Keyboard")
        const sessionButton = findItem(screen, "Select session")
        const powerRow = findItem(screen, "Reboot").parent
        if (powerRow.parent !== footer || powerRow.y !== keyboardButton.y + keyboardButton.height
                || (sessionButton.visible && powerRow.y + powerRow.height > sessionButton.y))
            throw new Error("Power controls must sit between keyboard and session")
    }
    function checkFeedbackMotion(screen, setMessage) {
        const status = root.findItem(screen, "authStatus")
        const field = root.findItem(screen, "authPassword")
        screen.animationsEnabled = true
        setMessage("Retry")
        keys.tryCompare(status, "opacity", 1, 400)
        setMessage("")
        keys.wait(30)
        if (!(status.opacity > 0 && status.opacity < 1))
            throw new Error("Feedback did not animate")
        setMessage("Retry") // Interrupt disappearance without delaying input.
        keys.tryCompare(status, "opacity", 1, 400)
        screen.animationsEnabled = false
        setMessage("")
        if (status.opacity !== 0) throw new Error("Disabled motion was not immediate")
        setMessage("Retry")
        if (status.opacity !== 1 || !field.activeFocus)
            throw new Error("Interrupted/reduced motion lost feedback or focus")
        screen.animationsEnabled = true
    }
    property int captures: 0
    function capture(item, name) {
        const directory = Quickshell.env("ICEWINE_PREVIEW_DIR")
        if (!directory) return
        ++captures
        item.grabToImage(result => {
            if (!result.saveToFile(directory + "/" + name + ".png"))
                throw new Error("Preview capture failed")
            --root.captures
        })
    }
    function authChild(predicate) {
        for (const child of auth.children ?? []) {
            if (predicate(child)) return child
        }
        return null
    }
    Timer {
        id: renderTimer
        interval: 100
        running: true
        repeat: true
        onTriggered: {
            renderTimer.stop()
            if (root.authChildren.length === 0) {
                const controller = auth.controller
                const inputPanel = Array.from(login.children).find(child => child.active !== undefined)
                if (controller.keyboardEnabled !== false || controller.keyboardVisible
                        || !inputPanel || inputPanel.visible)
                    throw new Error("SDDM keyboard must start hidden")
                if (inputPanel.width > 900 || inputPanel.width > login.width
                        || inputPanel.width > login.height * 1.5
                        || inputPanel.x !== (login.width - inputPanel.width) / 2)
                    throw new Error("SDDM keyboard size or centring failed")
                // Mock input-method activation; offscreen has no native OSK service.
                inputPanel.visible = Qt.binding(() => controller.keyboardEnabled)
                loginWindow.requestActivate()
                root.findItem(auth, "authPassword").forceActiveFocus()
                controller.toggleKeyboard(auth)
                keys.tryCompare(inputPanel, "visible", true)
                keys.wait(50)
                root.checkLayout(auth, inputPanel.height)
                if (!controller.keyboardEnabled)
                    throw new Error("SDDM keyboard explicit enable failed")
                controller.toggleKeyboard(auth)
                if (controller.keyboardEnabled || inputPanel.visible)
                    throw new Error("SDDM keyboard explicit disable failed")
                if (controller.userCount !== 2 || controller.userLabel !== "Peter"
                        || controller.sessionCount !== 2 || controller.sessionLabel !== "Hyprland")
                    throw new Error("SDDM model bindings failed")
                root.capture(auth, "login-dark-idle")
                keys.tryCompare(root, "captures", 0, 2000)
                controller.password = "discard-on-user-change"
                controller.nextUser()
                controller.nextSession()
                if (controller.password !== "" || controller.userLabel !== "guest")
                    throw new Error("SDDM user selection failed")
                controller.password = "test-secret"
                controller.submit()
                controller.submit()
                if (sddm.logins !== 1 || !controller.busy || controller.password !== "")
                    throw new Error("SDDM submission guard failed")
                sddm.loginFailed()
                if (controller.busy || !controller.failed)
                    throw new Error("SDDM failure recovery failed")
                controller.password = "test-secret"
                controller.submit()
                sddm.loginSucceeded()
                if (sddm.logins !== 2 || controller.failed || !controller.busy)
                    throw new Error("SDDM retry failed")
                if (typeof session.keyboardVisible !== "boolean"
                        || !Number.isFinite(session.keyboardHeight))
                    throw new Error("SessionControl keyboard bindings failed")
                controller.busy = false
                const field = root.findItem(auth, "authPassword")
                loginWindow.requestActivate()
                keys.tryCompare(loginWindow, "active", true)
                field.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab)
                if (!root.findItem(auth, "Continue").activeFocus)
                    throw new Error("Password Tab navigation failed: " + loginWindow.activeFocusItem)
                field.forceActiveFocus()
                controller.busy = false
                field.text = "test-secret"
                keys.keyClick(Qt.Key_Return)
                if (sddm.logins !== 3 || !controller.busy)
                    throw new Error("Password Return submission failed")
                sddm.loginFailed()
                keys.tryCompare(field, "activeFocus", true)
                if (field.text !== "" || !controller.failed)
                    throw new Error("Failure must clear and refocus password")
                root.checkFeedbackMotion(auth, message => { controller.message = message })
                root.checkLayout(auth, 0)
                root.capture(auth, "login-dark-desktop")
                const lockBackdrop = root.findItem(lockScreen, "authBackdrop")
                keys.tryCompare(lockBackdrop, "status", Image.Ready, 2000)
                keys.tryCompare(root.findItem(auth, "authBackdrop"), "status", Image.Ready, 2000)
                if (!String(lockBackdrop.source).includes("/icewine/wallpapers/auth.img"))
                    throw new Error("Lock override was not selected")
                resetOverride.running = true
                keys.tryCompare(resetOverride, "running", false)
                lockSession.wallpaperRevision = "reset"
                keys.tryCompare(lockBackdrop, "status", Image.Ready, 2000)
                keys.tryCompare(locker, "selectionAvailable", false)
                if (!String(lockBackdrop.source).endsWith("/wallpapers/default.jpg"))
                    throw new Error("Missing override/selection did not inherit default")
                selectDesktop.running = true
                keys.tryCompare(selectDesktop, "running", false)
                lockSession.wallpaperRevision = "desktop-change"
                keys.tryVerify(() => String(lockBackdrop.source).includes("/icewine/wallpapers/selection.img"), 2000)
                keys.tryCompare(lockBackdrop, "status", Image.Ready, 2000)
                login.wallpaperSource = Qt.resolvedUrl("missing-public.img")
                keys.tryCompare(login, "publicationAvailable", false, 2000)
                keys.tryCompare(root.findItem(auth, "authBackdrop"), "status", Image.Ready, 2000)
                if (!String(root.findItem(auth, "authBackdrop").source).endsWith("/wallpaper.png"))
                    throw new Error("SDDM did not fall back to its public default image")
                root.capture(lockWindow.contentItem, "lock-dark-deck")
                keys.tryCompare(root, "captures", 0, 2000)
                root.authChildren = Array.from(auth.children)
                session.keyboardHost = auth
                loginWindow.width = 800
                loginWindow.height = 600
                launcher.launchSteamGamescope()
                renderTimer.start()
                return
            }
            if (launcher.pendingSteamCommand !== null) { renderTimer.start(); return }
            if (!launcher.steamLaunching || !launcher.steamSplashVisible)
                throw new Error("Missing launch state after the placeholder's first frame")
            if (!JSON.parse(launcher.launchSteamGamescope()).pending)
                throw new Error("Repeated request was not guarded")
            if (root.launches === 0) {
                // The running Flatpak singleton opens an outer window after splash startup.
                compositor.toplevels = [{address: "0xouter", lastIpcObject: {class: "com.valvesoftware.Steam"}}]
                keys.tryCompare(launcher, "steamSplashVisible", false)
                if (launcher.steamLaunching || launcher.steamRequestPending
                        || launcher.pendingSteamCommand !== null || compositor.activated !== "0xouter")
                    throw new Error("Outside singleton did not complete the shared launch")
                const reused = JSON.parse(launcher.launchSteamGamescope())
                if (!reused.reused || !reused.outsideGamescope || launcher.steamSplashVisible)
                    throw new Error("Visible outside session was not identified/reused")
                launcher.steamRequestPending = true
                launcher.steamGamescopePid = 481
                compositor.toplevels = [{address: "0xnested", wayland: {appId: "gamescope"},
                    lastIpcObject: {pid: 481}}, ...compositor.toplevels]
                keys.tryCompare(compositor, "activated", "0xnested")
                if (launcher.steamRequestPending)
                    throw new Error("Managed nested reuse left a pending request")
                const nestedReuse = JSON.parse(launcher.launchSteamGamescope())
                if (!nestedReuse.reused || nestedReuse.outsideGamescope
                        || compositor.activated !== "0xnested")
                    throw new Error("Shared entry did not prefer the managed nested session")
                compositor.toplevels = []
                launcher.steamRequestPending = true
                launcher.resolveSteamRequest("unavailable")
                if (launcher.steamRequestPending || launcher.steamLaunching || launcher.steamSplashVisible)
                    throw new Error("Detection error retained launch state")
            } else {
                launcher.finishSteamLaunch()
            }
            if (launcher.steamLaunching || launcher.steamSplashVisible)
                throw new Error("Teardown did not clear launch state")
            if (++root.launches === 2) {
                const keyboard = root.authChild(item => !root.authChildren.includes(item))
                if (auth.scaleFactor !== 0.8)
                    throw new Error("Small-screen type scaling failed")
                if (!keyboard || keyboard.width !== Math.min(auth.width, 900, auth.height * 1.5)
                        || keyboard.x !== (auth.width - keyboard.width) / 2
                        || keyboard.y !== auth.height - keyboard.height
                        || session.keyboardHeight !== keyboard.height)
                    throw new Error("SessionControl keyboard host bindings failed")
                auth.palette = Theme.LightPalette
                lockScreen.palette = Theme.LightPalette
                keys.wait(50)
                root.checkLayout(auth, 0)
                root.capture(auth, "login-light-small")
                keys.tryCompare(root, "captures", 0, 2000)
                lockWindow.width = 800; lockWindow.height = 600
                const lockField = root.findItem(lockScreen, "authPassword")
                lockWindow.requestActivate()
                keys.tryCompare(lockWindow, "active", true)
                lockField.text = ""
                lockField.focus = false
                locker.forceActiveFocus()
                keys.wait(1)
                keys.keyClick(Qt.Key_A)
                if (!lockField.activeFocus || lockField.text !== "a" || lockSession.password !== "a")
                    throw new Error("First printable lock key must restore focus and arrive once")
                lockField.focus = false
                locker.forceActiveFocus()
                keys.wait(1)
                keys.keyClick(Qt.Key_Return)
                if (!lockField.activeFocus || lockSession.submissions !== 0 || lockField.text !== "a")
                    throw new Error("Neutral Enter must focus without submitting")
                lockField.focus = false
                locker.forceActiveFocus()
                keys.wait(1)
                keys.keyClick(Qt.Key_A, Qt.ControlModifier)
                if (!lockField.activeFocus || lockField.text !== "a" || lockField.selectedText !== "a")
                    throw new Error("Modified lock input must retain native text shortcuts")
                lockField.text = ""
                lockField.focus = false
                locker.forceActiveFocus()
                keys.wait(1)
                keys.keyPress(Qt.Key_Shift); keys.keyRelease(Qt.Key_Shift)
                if (!lockField.activeFocus || lockField.text || lockSession.submissions)
                    throw new Error("Modifier-only lock input must focus without text/submission")
                keys.keyClick(Qt.Key_Tab)
                if (!root.findItem(lockScreen, "Continue").activeFocus)
                    throw new Error("Lock password Tab must reach Continue")
                keys.keyClick(Qt.Key_Tab, Qt.ShiftModifier)
                if (!lockField.activeFocus) throw new Error("Lock Backtab must return to password")
                const lockKeyboardButton = root.findItem(lockScreen, "Keyboard")
                lockKeyboardButton.forceActiveFocus()
                keys.keyClick(Qt.Key_Tab)
                if (!root.findItem(lockScreen, "Reboot").activeFocus || lockField.activeFocus)
                    throw new Error("Footer Tab must retain explicit navigation")
                keys.keyClick(Qt.Key_Left)
                if (lockField.activeFocus) throw new Error("Footer navigation stole password focus")
                lockKeyboardButton.forceActiveFocus()
                keys.keyClick(Qt.Key_Space)
                if (!lockSession.keyboardVisible || !lockField.activeFocus)
                    throw new Error("Explicit footer keyboard activation was intercepted")
                lockKeyboardButton.forceActiveFocus()
                keys.keyClick(Qt.Key_Space)
                if (lockSession.keyboardVisible) throw new Error("Footer keyboard hide failed")
                lockSession.authenticating = true
                lockField.focus = false
                locker.forceActiveFocus()
                keys.wait(1)
                keys.keyClick(Qt.Key_C)
                if (lockField.text || lockSession.password || lockSession.submissions)
                    throw new Error("Busy lock surface must ignore password input")
                lockSession.authenticating = false
                lockField.forceActiveFocus()
                lockField.text = "mock-lock-secret"
                keys.keyClick(Qt.Key_Return)
                if (lockSession.submissions !== 1 || !lockSession.authenticating
                        || lockSession.password !== "" || !lockSession.locked)
                    throw new Error("Lock adapter submission bypassed session or retained password")
                lockSession.failed = true
                lockSession.authenticating = false
                keys.tryCompare(lockField, "activeFocus", true)
                root.checkFeedbackMotion(lockScreen, message => { lockSession.failed = Boolean(message) })
                root.findItem(lockScreen, "Keyboard").click()
                keys.wait(50)
                root.checkLayout(lockScreen, 280)
                root.capture(lockWindow.contentItem, "lock-light-small-keyboard")
                keys.tryCompare(root, "captures", 0, 2000)
                root.findItem(lockScreen, "Reboot").click()
                root.findItem(lockScreen, "Shutdown").click()
                if (lockSession.reboots !== 1 || lockSession.shutdowns !== 1)
                    throw new Error("Lock adapter power routing failed")
                root.findItem(lockScreen, "Keyboard").click()
                lockWindow.width = 320; lockWindow.height = 480
                keys.wait(50)
                root.checkLayout(lockScreen, 0)
                keys.tryCompare(root, "captures", 0, 2000)
                console.log("RENDER_READY_PASSED")
                Qt.quit()
            } else {
                launcher.launchSteamGamescope()
                renderTimer.start()
            }
        }
    }
}
"""

if native_adapter:
    # Qt permits one native InputPanel per process; reuse this fixture's adapters,
    # SDDM model mocks, layout assertions, palette generation and command sandbox.
    models = qml[qml.index("    ListModel {"):qml.index("    Window {")]
    helpers = qml[qml.index("    function findItem"):qml.index("    function authChild")]
    adapter = ("""Item {
        anchors.fill: parent
        property alias nativeController: session
        Modules.SessionControl { id: session; authenticationRequired: true }
        Modules.LockScreenSurface { anchors.fill: parent; session: session }
    }""" if native_adapter == "lock" else "Sddm.Main { anchors.fill: parent }")
    qml = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules" as Modules
import "sddm" as Sddm
import "theme" as Theme
ShellRoot {
    id: root
""" + models + helpers + """
    QtObject {
        id: config
        property string animations: ""
        function stringValue(key) { return animations }
    }
    Window {
        id: win; visible: true; width: 1920; height: 1080
        Loader { id: surface; anchors.fill: parent; sourceComponent: Component {
""" + adapter + """
        } }
        TestCase { id: keys; when: false }
    }
    Timer {
        interval: 100; running: true
        onTriggered: {
            try {
                win.requestActivate()
                keys.tryCompare(win, "active", true)
                const auth = root.findItem(surface.item, "authPanel").parent
                const field = root.findItem(auth, "authPassword")
                const button = root.findItem(auth, "Keyboard")
                const owner = surface.item.nativeController ?? auth.controller
                field.forceActiveFocus()
                // Keep the adapter palette identity shared with its native style.
                const livePalette = auth.palette
                const paletteRoles = ["background", "backgroundDark", "surface", "selection", "border", "foreground", "foregroundDark", "muted", "primary", "primaryDark", "secondary", "tertiary", "success", "warning", "caution", "error", "info"]
                const darkPalette = {}
                // QML colour values retain property references; snapshot their values.
                for (const role of paletteRoles) darkPalette[role] = String(livePalette[role])
                let keyboard
                if (owner.keyboardEnabled || owner.keyboardVisible)
                    throw new Error("Native keyboard must start explicitly disabled")
                for (const size of [[1920,1080], [1280,800], [800,600], [320,480]]) {
                    win.width = size[0]; win.height = size[1]
                    const sizePalette = size[0] < 1000 ? Theme.LightPalette : darkPalette
                    for (const role of paletteRoles) livePalette[role] = sizePalette[role]
                    keys.wait(50)
                    if (size[0] === 1280) {
                        root.capture(win.contentItem, "motion-" + Quickshell.env("ICEWINE_NATIVE_ADAPTER") + "-0")
                        keys.tryCompare(root, "captures", 0, 2000)
                    }
                    keys.mouseClick(button)
                    keyboard = Array.from(surface.item.children).concat(Array.from(auth.children))
                        .find(item => item.active !== undefined)
                    keys.tryCompare(keyboard, "visible", true, 2000, "Explicit native show")
                    keys.wait(30)
                    if (!(keyboard.opacity > 0 && keyboard.opacity < 1))
                        throw new Error("Native keyboard appearance did not animate")
                    if (size[0] === 1280) {
                        root.capture(win.contentItem, "motion-" + Quickshell.env("ICEWINE_NATIVE_ADAPTER") + "-1")
                        keys.tryCompare(root, "captures", 0, 2000)
                    }
                    keys.tryCompare(keyboard, "opacity", 1, 400)
                    if (size[0] === 1280) {
                        root.capture(win.contentItem, "motion-" + Quickshell.env("ICEWINE_NATIVE_ADAPTER") + "-2")
                        keys.tryCompare(root, "captures", 0, 2000)
                    }
                    const backdrop = root.findItem(keyboard, "icewineKeyboardBackground")
                    if (!backdrop || backdrop.color !== livePalette.backgroundDark)
                        throw new Error("Native keyboard did not load the Icewine palette style")
                    keys.tryCompare(field, "activeFocus", true)
                    function nativeKey(item, label) {
                        if (item.objectName === "icewineKeyboardKey" && item.label === label) return item
                        for (const child of item.children ?? []) {
                            const found = nativeKey(child, label)
                            if (found) return found
                        }
                        return null
                    }
                    const letter = nativeKey(keyboard, "a")
                    const backspace = nativeKey(keyboard, "⌫")
                    if (!letter || !backspace) throw new Error("Native key labels missing")
                    keys.wait(100)
                    const beforeClick = "theme-secret"
                    field.text = beforeClick
                    keys.mouseClick(letter)
                    if (field.text !== beforeClick + "a") throw new Error("Styled native key did not input once")
                    keys.mouseClick(backspace)
                    keys.wait(100)
                    if (field.text !== beforeClick) throw new Error("Styled native backspace did not delete once at " + size + " beforeLength=" + beforeClick.length + " afterLength=" + field.text.length)
                    const previousText = field.text
                    const previousColour = String(backdrop.color)
                    const changedPalette = size[0] < 1000 ? darkPalette : Theme.LightPalette
                    for (const role of ["backgroundDark", "surface", "selection", "border", "foreground", "primary"])
                        livePalette[role] = changedPalette[role]
                    keys.wait(10)
                    if (auth.palette !== livePalette || String(backdrop.color) === previousColour
                            || backdrop.color !== livePalette.backgroundDark || field.text !== previousText || !field.activeFocus)
                        throw new Error("Native live palette change: size=" + size + " identity=" + (auth.palette === livePalette) + " changed=" + (String(backdrop.color) !== previousColour) + " colour=" + (backdrop.color === livePalette.backgroundDark) + " text=" + (field.text === previousText) + " focus=" + field.activeFocus)
                    keys.tryCompare(field, "activeFocus", true)
                    keys.wait(50)
                    if (keyboard.width !== Math.min(win.width, 900, win.height * 1.5)
                            || keyboard.x !== (win.width - keyboard.width) / 2
                            || keyboard.height <= 0 || keyboard.y + keyboard.height > win.height)
                        throw new Error("Native keyboard bounds failed")
                    keys.wait(50)
                    root.checkLayout(auth, keyboard.height)
                    if (size[0] === 1280) {
                        root.capture(win.contentItem, "native-" + Quickshell.env("ICEWINE_NATIVE_ADAPTER"))
                        keys.tryCompare(root, "captures", 0, 2000)
                    }
                    keys.keyClick(Qt.Key_A)
                    if (!field.text.endsWith("a")) throw new Error("Password input lost focus")
                    keys.mouseClick(button)
                    keys.tryCompare(keyboard, "visible", false, 2000, "Explicit native hide")
                    win.contentItem.forceActiveFocus()
                    if (Quickshell.env("ICEWINE_NATIVE_ADAPTER") === "lock") {
                        field.focus = false
                        auth.parent.forceActiveFocus()
                        keys.wait(1)
                        const before = field.text
                        keys.keyClick(Qt.Key_B)
                        if (!field.activeFocus || field.text !== before + "b" || owner.password !== field.text)
                            throw new Error("Native lock first printable key lost/doubled input")
                    } else field.forceActiveFocus()
                    keys.wait(100)
                    if (owner.keyboardEnabled || owner.keyboardVisible || keyboard.visible)
                        throw new Error("Password refocus reopened dismissed native keyboard")
                    keys.mouseClick(button)
                    keys.tryCompare(keyboard, "visible", true)
                    Qt.inputMethod.hide() // Native HideKeyboardKey uses this same hide path.
                    keys.tryCompare(owner, "keyboardEnabled", false, 2000, "Native hide clears intent")
                    win.contentItem.forceActiveFocus()
                    field.forceActiveFocus()
                    keys.wait(100)
                    if (keyboard.visible) throw new Error("Native dismissal was not retained")
                    field.text = ""
                }
                if (surface.item.nativeController) auth.animationsEnabled = false
                else config.animations = "off"
                if (auth.animationsEnabled) throw new Error("Reduced motion was ignored")
                keys.mouseClick(button)
                keys.tryCompare(keyboard, "visible", true)
                if (keyboard.opacity !== 1) throw new Error("Disabled keyboard motion was not immediate")
                keys.mouseClick(button)
                if (keyboard.visible || keyboard.opacity !== 0)
                    throw new Error("Disabled keyboard dismissal was not immediate")
                console.log("RENDER_READY_PASSED")
                Qt.quit()
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
}
"""

if workspace_theme:
    qml = """import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "icewine/modules/topbar" as Topbar
import "theme" as Theme
ShellRoot {
    id: root
    QtObject { id: first; property bool activated: true; property var wayland: ({appId: ""}) }
    QtObject { id: second; property bool activated: false; property var wayland: ({appId: ""}) }
    QtObject { id: third; property bool activated: false; property var wayland: ({appId: ""}) }
    QtObject {
        id: compositor
        property var monitor: ({activeWorkspace: {id: 1}})
        property int requests: 0
        function monitorFor(screen) { return monitor }
        function workspaceIdsForMonitor(monitor) { return [1, 2, 3] }
        function toplevelsForWorkspace(id) { return id === 1 ? [first, second] : id === 2 ? [third] : [] }
        function activateWorkspace(id) { requests++; monitor = {activeWorkspace: {id: id}} }
    }
    Window {
        id: window
        visible: true; width: 640; height: 140
        color: Theme.Palette.background
        Rectangle { anchors.fill: parent; color: Theme.Palette.background }
        Text { x: 20; y: 15; text: "Active workspace / focused window · 2× preview"; color: Theme.Palette.foreground }
        Topbar.Workspaces { id: workspaces; x: 20; y: 65; scale: 2; transformOrigin: Item.TopLeft; compositor: compositor; screen: Quickshell.screens[0] }
        TestCase {
            id: keys
            when: false
            function descendants(item, predicate) {
                let result = predicate(item) ? [item] : []
                for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
                return result
            }
            function blend(colour, background) {
                return [colour.r, colour.g, colour.b].map((value, i) => colour.a * value + (1 - colour.a) * background[i])
            }
            function luminance(rgb) {
                return rgb.map(value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4))
                    .reduce((sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i], 0)
            }
            function contrast(colour, background) {
                const a = luminance([colour.r, colour.g, colour.b]), b = luminance(background)
                return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
            }
            function test_focusPresentation() {
                tryVerify(() => DesktopEntries.byId("workspace-test") !== null, 2000)
                for (const app of [first, second, third]) app.wayland = {appId: "workspace-test"}
                wait(100)
                const buttons = descendants(workspaces, item => item.workspaceId !== undefined)
                compare(buttons.length, 3)
                verify(buttons[0].active)
                verify(buttons[0].color.a < 0.3, "Workspace tint must stay subtle")
                const icons = descendants(workspaces, item => item.appId !== undefined)
                compare(icons.length, 3)
                compare(icons.filter(item => item.focused).length, 1)
                const backgrounds = icons.map(item => item.children.find(child => child.radius === 4))
                compare(backgrounds[0].color, Theme.Palette.primary)
                compare(backgrounds[1].color.a, 0)
                const base = blend(workspaces.color, [window.color.r, window.color.g, window.color.b])
                const activeBackground = blend(buttons[0].color, base)
                const label = descendants(buttons[0], item => item.text === "1")[0]
                verify(contrast(label.color, activeBackground) >= 4.5, "Workspace label contrast")
                const fallback = descendants(icons[0], item => item.text !== undefined)[0]
                verify(contrast(fallback.color, [backgrounds[0].color.r, backgrounds[0].color.g, backgrounds[0].color.b]) >= 4.5, "Focused fallback contrast")
                const images = descendants(workspaces, item => item.sourceSize !== undefined)
                for (const image of images) tryCompare(image, "status", Image.Ready, 2000)
                const directory = Quickshell.env("ICEWINE_PREVIEW_DIR")
                if (directory) {
                    let captured = false
                    verify(window.contentItem.grabToImage(result => {
                        verify(result.saveToFile(directory + "/workspaces.png"))
                        captured = true
                    }))
                    tryVerify(() => captured, 2000)
                }
                first.activated = false; second.activated = true
                wait(20)
                compare(backgrounds[0].color.a, 0)
                compare(backgrounds[1].color, Theme.Palette.primary)
                mouseClick(buttons[1])
                compare(compositor.requests, 1)
                compare(workspaces.activeId, 2)
                wait(150)
                verify(buttons[1].active)
                verify(buttons[1].color.a < 0.3)
                console.log("WORKSPACES_PASSED")
                Qt.quit()
            }
        }
        Timer {
            interval: 100; running: true; repeat: false
            onTriggered: {
                try { keys.test_focusPresentation() }
                catch (error) { console.error("Workspace check failed:", error); Qt.exit(1) }
            }
        }
    }
}
"""

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    style_root = root / "sddm" if native_adapter == "sddm" else root
    shutil.copytree(source / "quickshell/QtQuick", style_root / "QtQuick")
    if native_adapter == "sddm":
        style = style_root / "QtQuick/VirtualKeyboard/Styles/icewine/style.qml"
        style.chmod(style.stat().st_mode | 0o200)
        style.write_text(style.read_text().replace("import qs.icewine.theme as Theme", 'import IcewineTheme as Theme'))
    (root / "icewine").mkdir()
    (root / "icewine/modules").symlink_to(source / "quickshell/modules")
    (root / "icewine/theme").symlink_to(root / "theme")
    (root / "theme").mkdir()
    palette = (source / "theme/assets/templates/Palette.qml.in").read_text()
    # Mutable fixture tokens exercise native style updates without changing input state.
    for name, theme in [("Palette", workspace_theme or "tokyo-night"), ("LightPalette", "gruvbox-light")]:
        colours = json.loads((source / "theme/assets/themes" / (theme + ".json")).read_text())
        (root / "theme" / (name + ".qml")).write_text(
            re.sub(r"@(\w+)@", lambda match: colours[match[1]], palette)
                .replace("readonly property color", "property color"))
    (root / "theme/qmldir").write_text(
        "singleton Palette 1.0 Palette.qml\nsingleton LightPalette 1.0 LightPalette.qml\n")
    (root / "sddm").mkdir(exist_ok=True)
    shutil.copyfile(source / "sddm/Main.qml", root / "sddm/Main.qml")
    (root / "sddm/modules").symlink_to(source / "quickshell/modules")
    shutil.copytree(root / "theme", root / "sddm/theme")
    (style_root / "IcewineTheme").mkdir()
    palette_path = "../theme/Palette.qml" if native_adapter == "sddm" else "../sddm/theme/Palette.qml"
    (style_root / "IcewineTheme/qmldir").write_text(
        "module IcewineTheme\nsingleton Palette 1.0 " + palette_path + "\n")
    (root / "config").mkdir()
    (root / "config/qmldir").write_text("singleton Settings 1.0 Settings.qml\n")
    (root / "config/Settings.qml").write_text("""pragma Singleton
import QtQml
QtObject {
    readonly property bool authenticationRequired: false
}
""")
    if workspace_theme:
        (root / "data/applications").mkdir(parents=True)
        (root / "data/window.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect x="2" y="3" width="28" height="26" rx="3" fill="#3a82c3" stroke="#ffffff" stroke-width="2"/><path d="M3 10h26" stroke="#ffffff" stroke-width="2"/></svg>')
        (root / "data/applications/workspace-test.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Workspace fixture\nExec=true\nIcon=" + str(root / "data/window.svg") + "\n")
    (root / "data/wallpapers").mkdir(parents=True)
    (root / "data/wallpapers/default.jpg").symlink_to(source / "theme/assets/flower-branch.png")
    (root / "sddm/wallpaper.png").symlink_to(source / "theme/assets/flower-branch.png")
    (root / "public-auth.img").symlink_to(source / "theme/assets/flower-branch.png")
    (root / "data/icewine/wallpapers").mkdir(parents=True)
    (root / "data/icewine/wallpapers/auth.img").symlink_to(source / "theme/assets/flower-branch.png")
    (root / "bin").mkdir()
    for name, body in {
        "uwsm": 'printf "%s\\n" "$*" >> "$TEST_LAUNCHES"\n',
        "notify-send": 'printf "%s\\n" "$*" >> "$TEST_NOTIFICATIONS"\n',
        "icewine-monitor-capabilities": "exit 0\n",
        "systemctl": 'printf "LoadState=not-found\\nMainPID=0\\n"\n',
        "gdbus": '''if [[ "$1" == "call" ]]; then
    printf "(objectpath '/org/freedesktop/login1/session/_test',)\\n"
else
    exec sleep 10
fi
''',
    }.items():
        command = root / "bin" / name
        command.write_text("#!" + shutil.which("bash") + "\n" + body)
        command.chmod(0o700)
    (root / "shell.qml").write_text(qml)
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(runtime),
               QML_IMPORT_PATH=str(style_root),
               PATH=str(root / "bin") + os.pathsep + os.environ["PATH"],
               TEST_LAUNCHES=str(root / "launches"), TEST_NOTIFICATIONS=str(root / "notifications"), XDG_DATA_HOME=str(root / "data"))
    if workspace_theme:
        env["XDG_DATA_DIRS"] = str(root / "data")
    if native_adapter:
        env.update(QT_IM_MODULE="qtvirtualkeyboard", QT_VIRTUALKEYBOARD_DESKTOP_DISABLE="1",
                   ICEWINE_NATIVE_ADAPTER=native_adapter)
    if preview_dir:
        env["ICEWINE_PREVIEW_DIR"] = str(preview_dir)
    try:
        result = subprocess.run(["qs", "-p", str(root), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as error:
        raise AssertionError((error.stdout or b"") + (error.stderr or b"")) from error
    output = result.stdout + result.stderr
    assert result.returncode == 0 and ("WORKSPACES_PASSED" if workspace_theme else "RENDER_READY_PASSED") in output, output
    assert "Failed to load configuration" not in output, output
    assert not re.search(r"ReferenceError|TypeError|Binding loop|Unable to assign", output), output
    if workspace_theme:
        print("Workspace focus presentation passed:", workspace_theme)
        sys.exit(0)
    launches = [] if native_adapter else (root / "launches").read_text().splitlines()
    assert native_adapter or len(launches) == 2 and all(
        line.startswith("app -t service -u icewine-steam-gamescope.service "
                        "-p ExitType=main -p KillMode=control-group "
                        "-- gamescope ")
        for line in launches
    ), launches
    if not native_adapter:
        notifications = (root / "notifications").read_text().splitlines()
        assert len(notifications) == 2 and all(
            "Steam is already running outside Gamescope" in line
            and "Quit Steam manually" in line for line in notifications), notifications
    print(f"Native {native_adapter} OSK input, bounds, dismissal/refocus checks passed" if native_adapter
          else "Steam launch, auth visuals, locker and SDDM adapter checks passed")
