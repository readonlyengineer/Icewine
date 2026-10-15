// The real packaged Breeze form and keyboard; the fixture supplies SDDM's
// surrounding model/callback context. Actual greeter startup is checked separately.
import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.VirtualKeyboard
import QtTest
import org.kde.breeze.components as Breeze
import org.kde.ki18n
import "breeze" as Native

Window {
    id: root
    visible: true; width: 1280; height: 800
    property int requests: 0
    property string submittedUser: ""
    property string submittedPassword: ""
    readonly property KI18nContext translations: KI18nContext { translationDomain: "plasma-desktop-sddm-theme" }
    function i18n(...args) { return translations.i18n(...args) }
    function i18nc(...args) { return translations.i18nc(...args) }
    function i18nd(...args) { return translations.i18nd(...args) }
    function i18ndc(...args) { return translations.i18ndc(...args) }
    QtObject { id: sddm; signal loginFailed() }
    Item { id: footer }
    ListModel {
        id: users
        ListElement { name: "demo"; realName: "Demo"; icon: ""; needsPassword: true }
        ListElement { name: "other"; realName: "Other"; icon: ""; needsPassword: true }
    }
    QQC2.StackView {
        id: mainStack
        width: parent.width; height: parent.height + 54
        focus: true
        initialItem: Native.Login {
            id: userListComponent
            loginScreenUiVisible: true
            showUserList: true
            userListModel: users
            userListCurrentIndex: 0
            // Main.qml supplies native actions; the shared layout sizes its first child.
            actionItems: [
                Breeze.ActionButton { icon.name: "system-reboot"; text: "Restart" },
                Breeze.ActionButton { icon.name: "system-shutdown"; text: "Shut Down" }
            ]
            onLoginRequest: (username, password) => {
                ++root.requests
                root.submittedUser = username
                root.submittedPassword = password
            }
        }
    }
    Breeze.VirtualKeyboardLoader {
        id: panel
        screenRoot: root.contentItem
        mainStack: mainStack
        mainBlock: mainStack.currentItem
        passwordField: mainStack.currentItem.mainPasswordBox
    }
    TestCase { id: keys; when: false }
    function find(item, predicate) {
        if (predicate(item)) return item
        for (const child of item.children ?? []) {
            const match = find(child, predicate)
            if (match) return match
        }
        return null
    }
    Timer {
        interval: 200; running: true
        onTriggered: {
            try {
                root.requestActivate()
                keys.tryCompare(root, "active", true)
                const form = mainStack.currentItem
                const field = form.mainPasswordBox
                field.forceActiveFocus()
                keys.keyClick(Qt.Key_A)
                keys.compare(field.text, "a", "native login first character")
                keys.keyClick(Qt.Key_Return)
                keys.compare(root.requests, 1)
                keys.compare(root.submittedUser, "demo")
                keys.compare(root.submittedPassword, "a")
                keys.verify(!mainStack.enabled && !footer.enabled, "native busy state")
                keys.compare(field.text, "", "packaged native login clears submitted password")
                keys.keyClick(Qt.Key_Return)
                keys.compare(root.requests, 1, "busy prevents duplicate")
                mainStack.enabled = true; footer.enabled = true
                sddm.loginFailed()
                keys.tryCompare(field, "activeFocus", true)
                keys.compare(field.text, "", "failure clears and refocuses")
                form.userListCurrentIndex = 1
                keys.wait(50)
                field.forceActiveFocus()
                for (const size of [[1280,800], [800,600], [320,480]]) {
                    root.width = size[0]; root.height = size[1]
                    keys.wait(50)
                    panel.showHide()
                    keys.tryCompare(panel, "keyboardActive", true, 2000)
                    keys.wait(300)
                    const letter = find(panel, item => item.keyType === QtVirtualKeyboard.KeyType.Key && item.text === "a")
                    keys.verify(letter, "native login OSK key loaded")
                    field.text = "test"
                    keys.mouseClick(letter)
                    keys.tryCompare(field, "text", "testa")
                    const position = field.mapToItem(root.contentItem, 0, 0)
                    keys.verify(position.y >= 0 && position.y + field.height <= root.height - panel.height,
                        "native login field above keyboard")
                    panel.showHide()
                    keys.tryCompare(panel, "keyboardActive", false, 2000)
                    field.forceActiveFocus()
                }
                field.text = "correct-fixture-response"
                keys.keyClick(Qt.Key_Return)
                keys.compare(root.requests, 2)
                keys.compare(root.submittedUser, "other", "native user model selection")
                keys.compare(root.submittedPassword, "correct-fixture-response")
                keys.compare(field.text, "", "retry clears password")
                console.log("BREEZE_LOGIN_PASSED")
                Qt.quit()
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
}
