#!/usr/bin/env python3
"""Run the real switcher QML with synthetic native-object stand-ins and offscreen Qt.
Run: python3 tests/window-switcher.py . (qs on PATH).
"""
import os
from pathlib import Path
from qml_fixture import theme_fixture
import re
import shutil
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
qml = '''import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtTest
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import qs.config as Config
import "icewine/modules" as Modules
ShellRoot {
    id: shell
    Modules.SessionControl { id: mockSession; authenticationRequired: true }
    QtObject { id: mockNotifications }
    Modules.NotificationService { id: notificationService }
    Modules.Topbar {
        id: topbar
        compositor: mockCompositor
        notificationService: mockNotifications
        session: mockSession
        sessionLocked: mockSession.locked
        function focusedScreenName() { return "DP-1" } // Offscreen output has no name.
    }
    Process {
        id: preferenceWriter
        command: ["python3", "-c",
            "import os,sys; p=sys.argv[1]; open(p+'.next','w').write(sys.argv[2]); os.replace(p+'.next',p)",
            Quickshell.env("XDG_STATE_HOME") + "/icewine/widgets.json", preferenceWriter.contents]
        property string contents: ""
    }
    QtObject {
        id: mockCompositor
        property var toplevels: [a, b, c]
        property string activeWindowAddress: "0x2"
        property bool suppressed: false
        property string restored: ""
        signal navigationRequested()
        signal monitorsChanged()
        signal configReloaded()
        function supress_mouse_binds(value) { suppressed = value }
        function activateWindow(address) { restored = address }
        function monitorFor(screen) { return {focused:true} }
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
        // The real Topbar loader, in panel-local logical coordinates. Native
        // layer surfaces and input regions still require compositor checks.
        Item {
            id: geometryHost
            x: 137; y: 91
            width: 1920; height: 1080
            property var screen: ({name: "DP-1"})
            property bool widgetHere: false
            __SIZING_LOADER__
        }
        Component {
            id: fixtureWindow
            QtObject {
                property string address
                property string title
                property var workspace
                property var wayland: null
            }
        }
        Button { id: otherControl; text: "Other top-bar control" }
        TestCase {
            id: keys
            when: false
            function descendants(item, predicate) {
                let result = predicate(item) ? [item] : []
                for (const child of item.children ?? []) result = result.concat(descendants(child, predicate))
                return result
            }
            function selectedCardVisible(target = loader) {
                const card = descendants(target.item, item => item.modelData === target.item.selected
                    && item.border !== undefined)[0]
                if (!card) return false
                const position = card.mapToItem(target.item, 0, 0)
                return position.x >= 16 && position.x + card.width <= target.width - 15
                    && position.y >= 16 && position.y + card.height <= target.height - 15
            }
            function centeredAndBounded() {
                return Math.abs(sizedLoader.x * 2 + sizedLoader.width - geometryHost.width) < 1
                    && Math.abs(sizedLoader.y * 2 + sizedLoader.height - geometryHost.height) < 1
                    && sizedLoader.x >= Math.min(24, geometryHost.width / 20) - 1
                    && sizedLoader.y >= Math.min(24, geometryHost.height / 20) - 1
                    && sizedLoader.width <= 1000 && sizedLoader.height <= 720
                    && sizedLoader.width <= geometryHost.width && sizedLoader.height <= geometryHost.height
            }
            function sizing() {
                geometryHost.widgetHere = true
                topbar.openWidget("switcher", true, "DP-1")
                tryVerify(() => sizedLoader.item !== null)
                const view = sizedLoader.item
                tryVerify(centeredAndBounded)
                verify(sizedLoader.width >= 360 && sizedLoader.width < 500)
                verify(sizedLoader.height >= 100 && sizedLoader.height < 200)
                const emptyHeight = sizedLoader.height
                mockCompositor.toplevels = [a]
                tryVerify(() => sizedLoader.height > emptyHeight)
                const singleWidth = sizedLoader.width
                const singleHeight = sizedLoader.height
                mockCompositor.toplevels = [a, b, d]
                tryVerify(() => sizedLoader.width > singleWidth)
                compare(sizedLoader.height, singleHeight)
                mockCompositor.toplevels = [a, b, d, c]
                tryVerify(() => sizedLoader.height > singleHeight)
                const many = []
                for (let row = 1; row <= 8; ++row)
                    for (let column = 0; column < 12; ++column)
                        many.push(fixtureWindow.createObject(window, {
                            address: row + ":" + column, title: "Window " + row + ":" + column,
                            workspace: {id: row, name: String(row), monitor: {name: "DP-1"}}}))
                mockCompositor.toplevels = many
                tryCompare(sizedLoader, "width", 1000)
                tryCompare(sizedLoader, "height", 720)
                // Both Topbar modes share geometry; shrink/grow the logical output
                // (including a scaled small output) while selection is offscreen.
                for (const fullWidth of [false, true]) {
                    topbar.fullWidth = fullWidth
                    for (const size of [[1920,1080], [420,280], [320,200], [1280,720]]) {
                        geometryHost.width = size[0]; geometryHost.height = size[1]
                        view.selected = many[many.length - 1]
                        tryVerify(centeredAndBounded)
                        tryVerify(() => selectedCardVisible(sizedLoader), 2000,
                            "Last card visible after output resize")
                        view.navigate(0, -1)
                        tryVerify(() => selectedCardVisible(sizedLoader), 2000,
                            "Workspace navigation scrolls selected card into view")
                        view.navigate(-1, 0)
                        tryVerify(() => selectedCardVisible(sizedLoader))
                        const scrolls = descendants(view, item => item.contentX !== undefined
                            && item.contentY !== undefined)
                        for (const scroll of scrolls) {
                            verify(scroll.contentX >= -1 && scroll.contentY >= -1)
                            verify(scroll.contentX <= Math.max(0, scroll.contentWidth - scroll.width) + 1)
                            verify(scroll.contentY <= Math.max(0, scroll.contentHeight - scroll.height) + 1)
                        }
                    }
                }
                geometryHost.width = 1920; geometryHost.height = 1080
                mockCompositor.toplevels = [a]
                tryCompare(sizedLoader, "width", singleWidth)
                tryCompare(sizedLoader, "height", singleHeight)
                tryVerify(() => selectedCardVisible(sizedLoader))
                mockCompositor.toplevels = []
                tryCompare(sizedLoader, "height", emptyHeight)
                tryCompare(view, "selected", null)
                tryVerify(centeredAndBounded)
                topbar.dismissWidget()
                tryVerify(() => sizedLoader.item === null, 2000, "Closing destroys preview owner")
                geometryHost.widgetHere = false
                for (const item of many) item.destroy()
                console.log("SWITCHER_SIZING_PASSED")
            }
            function check() {
                // Keep the real session/PAM-result handlers and topbar bindings.
                // Only native lock delivery is replaced: acquisition notifies,
                // unlock changes the getter without a notification (qs 0.3.2).
                mockSession.fixtureNativeLock = {locked: true, secure: true}
                verify(mockSession.locked, "A native lock still guards UI without recorded intent")
                mockSession.fixtureNativeLock = {locked: false, secure: false}
                for (let cycle = 0; cycle < 3; ++cycle) {
                    mockCompositor.restored = ""
                    topbar.openWidget("launcher", true, "DP-1")
                    topbar.pressBar()
                    verify(topbar.barVisible && topbar.widgetEngaged)
                    mockSession.lockFromLogind()
                    verify(mockSession.locked && mockSession.lockRequested)
                    verify(!topbar.barVisible && !topbar.widgetEngaged)
                    compare(topbar.ui.page, "")
                    verify(!topbar.ui.held && !mockCompositor.suppressed)
                    topbar.pressBar()
                    topbar.toggleSwitcher()
                    topbar.openWidget("audio", true, "DP-1")
                    verify(!topbar.barVisible && !topbar.ui.held && !topbar.ui.page)
                    mockSession.password = "fixture response"
                    mockSession.authenticating = true
                    mockSession.fixturePam.completed(PamResult.Success + 1)
                    verify(mockSession.locked && mockSession.failed && !mockSession.password)
                    verify(!mockSession.authenticating && !topbar.barVisible)
                    mockSession.authenticating = true
                    mockSession.fixturePam.completed(PamResult.Success)
                    verify(!mockSession.locked && !mockSession.lockRequested,
                        "Successful unlock releases every UI guard without native notify")
                    verify(!mockSession.password && !mockSession.failed && !mockSession.authenticating)
                    wait(1)
                    compare(mockCompositor.restored, "", "Lock handoff cancels old focus restoration")
                    topbar.pressBar()
                    verify(topbar.barVisible && topbar.ui.held, "Hold opens after unlock")
                    topbar.releaseBar()
                    verify(!topbar.barVisible && !topbar.ui.held, "Release hides after unlock")
                    topbar.toggleSwitcher()
                    compare(topbar.ui.page, "switcher")
                    topbar.toggleSwitcher()
                    compare(topbar.ui.page, "")
                    for (const page of ["launcher", "audio", "network", "bluetooth", "battery",
                            "performance", "layout", "screenshot"]) {
                        topbar.openWidget(page, true, "DP-1")
                        compare(topbar.ui.page, page, "Configured page opens after unlock")
                        topbar.dismissWidget()
                    }
                }
                mockSession.lockRequested = true
                verify(mockSession.locked, "Pending acquisition already guards UI")
                topbar.pressBar()
                verify(!topbar.barVisible && !topbar.ui.held)
                mockSession.lockRequested = false
                console.log("SESSION_LOCK_GUARDS_PASSED")
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
                otherControl.forceActiveFocus()
                tryVerify(() => otherControl.activeFocus)
                keyClick(Qt.Key_Escape)
                compare(window.dismissals, 2, "Escape dismisses after focus leaves the window cards")
                view.forceActiveFocus()
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
                const selectedCard = descendants(view, item => item.modelData === c && item.border !== undefined)[0]
                otherControl.forceActiveFocus()
                mouseClick(selectedCard, selectedCard.width / 2, selectedCard.height / 2)
                compare(view.selected, c)
                tryVerify(() => view.activeFocus, 2000, "Visible card click restores selector focus on 420x280")
                mockCompositor.toplevels = []
                tryVerify(() => view.rows.length === 0)
                keyClick(Qt.Key_Return)
                compare(window.activations, 1, "Empty switcher cannot activate a stale selection")
                sizing()
                // Actual settings watcher and retained service/controller state;
                // native layer/capture teardown remains a real-session check.
                mockCompositor.toplevels = [b]
                verify(Config.Settings.notificationToasts && Config.Settings.windowSwitcher)
                notificationService.popups = [{transient:false, tracked:true}]
                topbar.openWidget("switcher", true, "DP-1")
                verify(topbar.widgetEngaged && mockCompositor.suppressed)
                preferenceWriter.contents = '{"notificationToasts":false,"windowSwitcher":false}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                tryVerify(() => !Config.Settings.windowSwitcher)
                compare(topbar.ui.page, "")
                verify(!topbar.widgetEngaged && !mockCompositor.suppressed)
                tryCompare(mockCompositor, "restored", "0x2")
                compare(notificationService.popups.length, 0)
                topbar.openWidget("switcher", true, "DP-1")
                compare(topbar.ui.page, "", "Disabled switcher cannot reopen")
                preferenceWriter.contents = '{"windowSwitcher":"false"}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                wait(100)
                verify(!Config.Settings.windowSwitcher)
                preferenceWriter.contents = '{"notificationToasts":true,"windowSwitcher":true}'
                preferenceWriter.running = true
                tryVerify(() => !preferenceWriter.running)
                tryVerify(() => Config.Settings.windowSwitcher)
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
    # Disposable QML copies must be writable even when source is in the store.
    shutil.copytree(source / 'quickshell/modules', root / 'icewine/modules', copy_function=shutil.copyfile)
    notification_source = root / 'icewine/modules/NotificationService.qml'
    notification_source.write_text(notification_source.read_text().replace(
        "import Quickshell.Services.Notifications", "import NotificationFixtures"))
    fixtures = root / 'NotificationFixtures'
    fixtures.mkdir()
    (fixtures / 'qmldir').write_text("module NotificationFixtures\nNotificationServer 1.0 NotificationServer.qml\n")
    (fixtures / 'NotificationServer.qml').write_text("""import Quickshell
Scope {
    property var trackedNotifications: ({values:[]})
    property bool keepOnReload: false
    property bool persistenceSupported: false
    property bool actionsSupported: false
    property bool imageSupported: false
    signal notification(var notification)
}
""")
    session_source = root / 'icewine/modules/SessionControl.qml'
    native_session = session_source.read_text()
    # A JS object's fields have no QML notifier. Replacing the object on acquire
    # but mutating it on unlock models the native getter/NOTIFY mismatch, without
    # acquiring a compositor lock or starting a PAM conversation. An alias read
    # is represented by its equivalent binding so it can target the JS getter.
    native_session = native_session.replace('property alias locked: sessionLock.locked',
        'readonly property bool locked: sessionLock.locked')
    native_session = native_session.replace('    property string password: ""',
        '    property var fixtureNativeLock: ({locked: false, secure: false})\n'
        '    readonly property var fixturePam: pam\n    property string password: ""')
    native_session, count = re.subn(r'^        WlSessionLock \{[\s\S]*?^        \}', '''        Connections {
            target: lockState
            function onAcquiredChanged() {
                if (lockState.acquired) root.fixtureNativeLock = {locked: true, secure: true}
                else {
                    root.fixtureNativeLock.locked = false
                    root.fixtureNativeLock.secure = false
                }
            }
        }''', native_session, flags=re.M)
    assert count == 1, 'Expected one native session-lock boundary'
    session_source.write_text(native_session.replace('sessionLock.', 'root.fixtureNativeLock.'))
    topbar_source = root / 'icewine/modules/Topbar.qml'
    native_topbar = topbar_source.read_text()
    # Keep actual shared state/IPC/settings methods without Wayland panels or
    # host metric discovery. This does not establish real compositor capture.
    loader_start = native_topbar.index("                Loader {\n                    id: switcher")
    loader_end = native_topbar.index("                Bar.StatusPopout {", loader_start)
    sizing_loader = native_topbar[loader_start:loader_end].replace("id: switcher", "id: sizedLoader")
    sizing_loader = sizing_loader.replace("root.", "topbar.").replace("panel.", "geometryHost.")
    sizing_loader = sizing_loader.replace("sourceComponent: WindowSwitcher {", "sourceComponent: Modules.WindowSwitcher {")
    panel_start = native_topbar.index("    Variants {")
    panel_end = native_topbar.index("    IpcHandler {", panel_start)
    topbar_source.write_text((native_topbar[:panel_start]
        + "    QtObject { id: panels; property var instances: [] }\n"
        + native_topbar[panel_end:]).replace("Bar.SystemMetrics { id: metrics }", "QtObject { id: metrics }"))
    (root / 'icewine/theme').symlink_to(root / 'theme')
    (root / 'config').symlink_to(source / 'quickshell/config')
    fixture_config = theme_fixture(source, root)
    (root / 'shell.qml').write_text(qml.replace("__SIZING_LOADER__", sizing_loader))
    (root / 'runtime').mkdir(mode=0o700)
    (root / 'state/icewine').mkdir(parents=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QML_IMPORT_PATH=str(root),
               HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='',
               DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(root / 'no-session-bus'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'no-system-bus'),
               XDG_CACHE_HOME=str(root / 'cache'), XDG_RUNTIME_DIR=str(root / 'runtime'),
               XDG_STATE_HOME=str(root / 'state'), ICEWINE_WIDGET_POLICY='{}')
    env["XDG_CONFIG_HOME"] = fixture_config
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'SWITCHER_PASSED' in output and 'SWITCHER_SIZING_PASSED' in output, output
    assert not re.search(r'ReferenceError|TypeError|Binding loop|Unable to assign|not a type', output), output
    # One lightweight mixed policy case exercises both fixed directions against
    # opposing saved choices; nullable user choice was covered by the watcher.
    (root / 'state/icewine/widgets.json').write_text('{"notificationToasts":false,"windowSwitcher":true}')
    (root / 'shell.qml').write_text("""import QtQuick
import Quickshell
import qs.config as Config
ShellRoot {
    Timer {
        interval: 100; running: true
        onTriggered: {
            Config.Settings.widgetsFile.waitForJob()
            if (!Config.Settings.notificationToasts || Config.Settings.windowSwitcher) Qt.exit(1)
            else { console.log("MIXED_POLICY_PASSED"); Qt.quit() }
        }
    }
}
""")
    env["ICEWINE_WIDGET_POLICY"] = '{"notificationToasts":true,"windowSwitcher":false}'
    result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'MIXED_POLICY_PASSED' in result.stdout + result.stderr, result.stdout + result.stderr
    print('Switcher sizing, scrolling, keys, widget policy and repeated lock/unlock UI guards pass')
