import QtQuick
import QtQuick.Controls as Controls
import QtQuick.VirtualKeyboard
import "modules" as Modules
import "theme" as Theme
import "modules/WinterModel.js" as WinterModel

Item {
    id: root

    // Use Qt's model role lookup and selection; WinterScreen supplies the buttons.
    Controls.ComboBox {
        id: users
        visible: false
        model: userModel
        textRole: "realName"
        valueRole: "name"
        currentIndex: Math.max(0, userModel.lastIndex)
    }
    Controls.ComboBox {
        id: sessions
        visible: false
        model: sessionModel
        textRole: "name"
        currentIndex: Math.max(0, sessionModel.lastIndex)
    }

    QtObject {
        id: controller
        readonly property int userCount: users.count
        readonly property int sessionCount: sessions.count
        readonly property string userLabel: users.currentText || users.currentValue || "No users"
        readonly property string sessionLabel: sessions.currentText
        property string password: ""
        readonly property bool authenticationRequired: true
        property bool busy: false
        property bool failed: false
        readonly property bool secretInput: true
        readonly property string prompt: "Password"
        property string message: ""
        readonly property var keyboardHost: screen
        readonly property bool keyboardVisible: keyboard.active
        readonly property real keyboardHeight: keyboard.height
        readonly property bool canReboot: sddm.canReboot
        readonly property bool canShutdown: sddm.canPowerOff

        function nextUser() {
            users.currentIndex = WinterModel.nextIndex(users.currentIndex, users.count)
            password = ""
            message = ""
            failed = false
        }
        function nextSession() {
            sessions.currentIndex = WinterModel.nextIndex(sessions.currentIndex, sessions.count)
        }
        function submit() {
            if (busy || !users.currentValue || sessions.currentIndex < 0)
                return
            busy = true
            failed = false
            message = "Authenticating…"
            sddm.login(users.currentValue, password, sessions.currentIndex)
            password = ""
        }
        function requestReboot() { sddm.reboot() }
        function requestShutdown() { sddm.powerOff() }
        function toggleKeyboard(host) {
            if (keyboardVisible) Qt.inputMethod.hide()
            else Qt.inputMethod.show()
        }
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            controller.password = ""
            controller.busy = false
            controller.failed = true
            controller.message = "Login failed"
        }
        function onLoginSucceeded() {
            controller.message = "Starting session…"
        }
    }

    Modules.WinterScreen {
        id: screen
        anchors.fill: parent
        controller: controller
        palette: Theme.Palette
    }
    InputPanel {
        id: keyboard
        width: parent.width
        y: parent.height - height
        visible: active
    }
}
