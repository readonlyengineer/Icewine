import QtQuick
import QtQuick.Controls as Controls
import QtQuick.VirtualKeyboard
import "modules" as Modules
import "theme" as Theme
import "modules/AuthModel.js" as AuthModel

Item {
    id: root

    // Use Qt's model role lookup and selection; AuthScreen supplies the buttons.
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
        property bool keyboardEnabled: false
        readonly property bool keyboardVisible: keyboard.visible
        readonly property real keyboardHeight: keyboard.height
        readonly property bool canReboot: sddm.canReboot
        readonly property bool canShutdown: sddm.canPowerOff

        function nextUser() {
            users.currentIndex = AuthModel.nextIndex(users.currentIndex, users.count)
            password = ""
            message = ""
            failed = false
        }
        function nextSession() {
            sessions.currentIndex = AuthModel.nextIndex(sessions.currentIndex, sessions.count)
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
            keyboardEnabled = !keyboardEnabled
            if (keyboardEnabled) Qt.inputMethod.show()
            else Qt.inputMethod.hide()
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

    Modules.AuthScreen {
        id: screen
        anchors.fill: parent
        controller: controller
        palette: Theme.Palette
    }
    InputPanel {
        id: keyboard
        width: Math.min(parent.width, 900, parent.height * 1.5)
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height - height
        visible: active && controller.keyboardEnabled
    }
}
