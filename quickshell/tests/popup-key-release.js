// Run: node quickshell/tests/popup-key-release.js
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")

const cases = [
    ["Launcher.qml", "search", "launchKey", ["Return", "Enter"], "launch"],
    ["Widget.qml", "viewport", "escapeHeld", ["Escape"], "dismissRequested"],
    ["BackgroundApps.qml", "apps", "activationKey", ["Return", "Enter"], "openItem"],
    ["BackgroundApps.qml", "menuEntries", "activationKey", ["Return", "Enter", "Right"], "trigger"],
    ["popouts/ActionButton.qml", "root", "activationKey", ["Return", "Enter"], "click"]
]
const Qt = { Key_Return: 13, Key_Enter: 14, Key_Escape: 27, Key_Right: 39, Key_Tab: 9 }
for (const [file, id, state, keys, action] of cases) {
    const source = fs.readFileSync(path.join(__dirname, "../modules/topbar", file), "utf8")
    const section = source.slice(source.indexOf(`id: ${id}\n`))
    const control = { [state]: state === "escapeHeld" ? false : 0 }
    let actions = 0
    const root = { [action]: () => {
        assert.ok(!control[state], "Clear the key before transferring focus")
        actions++
    } }
    const context = vm.createContext({
        Qt, root, [id]: id === "root" ? Object.assign(control, root) : control,
        activeFocus: true, results: {currentItem: {entry: {}}},
        currentItem: {trayEntry: {}, menuEntry: {}}
    })
    Object.defineProperty(context, state, {
        get: () => control[state], set: value => { control[state] = value }
    })
    const releaseBody = section.match(/Keys\.onReleased: event => \{([\s\S]*?)\n\s*\}/)[1]
    const release = vm.runInContext(`event => {${releaseBody}}`, context)
    const focusReset = section.match(/onActiveFocusChanged: ([^\n]+)/)[1]
    const event = (key, repeat = false) => ({key, isAutoRepeat: repeat, accepted: false})
    for (const key of keys) {
        actions = 0
        const code = section.match(new RegExp(`Keys\\.on${key}Pressed: event => \\{([^\\n]+)\\}`))[1]
        const press = vm.runInContext(`event => {${code}}`, context)
        const keycode = Qt[`Key_${key}`]
        release(event(keycode)) // Opening key's release, without a press in this control.
        press(event(keycode, true)) // Repeat after focus arrived must not arm an action.
        release(event(keycode))
        assert.equal(actions, 0)
        press(event(keycode))
        for (let i = 0; i < 4; i++) {
            press(event(keycode, true))
            release(event(keycode, true))
        }
        release(event(Qt.Key_Tab))
        assert.equal(actions, 0, `${file}: a held key must not transfer focus`)
        const released = event(keycode)
        release(released)
        assert.equal(released.accepted, true)
        assert.equal(actions, 1, `${file}: release must act once`)
        release(event(keycode))
        assert.equal(actions, 1)
        press(event(keycode))
        context.activeFocus = false
        vm.runInContext(focusReset, context)
        context.activeFocus = true
        release(event(keycode))
        assert.equal(actions, 1, `${file}: focus loss must cancel the pending action`)
    }
}
console.log("popup keys: press, hold, release, opening-key and focus-loss checks pass")
