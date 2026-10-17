// US ANSI legends. Modifiers are UI latches; each emitted chord is balanced.
var shift = 0x02000000, control = 0x04000000, alt = 0x08000000, meta = 0x10000000
function special(label, symbol, code, units, repeat) {
    return { label: label, symbol: symbol, key: 0x01000000 + code, units: units || 1, repeat: !!repeat }
}
function character(text, upper, units) {
    return { label: text, text: text, upper: upper || text.toUpperCase(), key: text.toUpperCase().charCodeAt(0), units: units || 1, repeat: true }
}
function modifier(label, mask, units) { return { label: label, modifier: mask, units: units || 1 } }
var rows = [
    [special("Esc", "Escape", 0)].concat(Array.from({length:12}, (_, i) => special("F"+(i+1), "F"+(i+1), 0x30+i)),
        [special("Print", "Print", 9), special("Scroll", "Scroll_Lock", 0x26), special("Del", "Delete", 7, 1, true)]),
    [character("`", "~")].concat(Array.from("1234567890", (c,i) => character(c, "!@#$%^&*()"[i])),
        [character("-", "_"), character("=", "+"), special("Backspace", "BackSpace", 3, 2, true), special("Home", "Home", 0x10)]),
    [special("Tab", "Tab", 1, 1.5)].concat(Array.from("qwertyuiop", c => character(c)),
        [character("[", "{"), character("]", "}"), character("\\", "|", 1.5), special("PgUp", "Prior", 0x16, 1, true)]),
    [{label:"Caps", caps:true, units:1.75}].concat(Array.from("asdfghjkl", c => character(c)),
        [character(";", ":"), character("'", '"'), special("Enter", "Return", 4, 2.25), special("PgDn", "Next", 0x17, 1, true)]),
    [modifier("Shift", shift, 2.25)].concat(Array.from("zxcvbnm", c => character(c)),
        [character(",", "<"), character(".", ">"), character("/", "?"), modifier("Shift", shift, 1.75), special("↑", "Up", 0x13, 1, true), special("End", "End", 0x11)]),
    [modifier("Ctrl", control, 1.25), modifier("Super", meta, 1.25), modifier("Alt", alt, 1.25), character(" ", " ", 6.25),
        modifier("Alt", alt), special("Menu", "Menu", 0x55), modifier("Ctrl", control), special("←", "Left", 0x12, 1, true), special("↓", "Down", 0x15, 1, true), special("→", "Right", 0x14, 1, true)]
]
var keys = []
rows.forEach((row, r) => {
    var column = 0
    row.forEach(k => { k.row = r; k.column = column; k.index = keys.length; column += k.units; keys.push(k) })
})
function text(key, modifiers, caps) {
    if (key.text === undefined) return ""
    var uppercase = !!(modifiers & shift)
    if (/^[a-z]$/.test(key.text)) uppercase = uppercase !== caps
    return uppercase ? key.upper : key.text
}
function action(key, modifiers, caps) {
    return { key: key.key, text: text(key, modifiers, caps), symbol: key.symbol || "", modifiers: modifiers }
}
function command(event) {
    var args = ["timeout", "--kill-after=1s", "2s", "wtype"]
    var mods = [[shift,"shift"], [control,"ctrl"], [alt,"alt"], [meta,"logo"]].filter(pair => event.modifiers & pair[0])
    // Text has its own keysym in wtype's generated map; choose the displayed
    // symbol explicitly. Still send Shift as a modifier for app shortcuts.
    mods.forEach(pair => args.push("-M", pair[1]))
    if (event.text !== "") args.push("-k", "U" + event.text.codePointAt(0).toString(16).padStart(4,"0"))
    else args.push("-k", event.symbol)
    mods.slice().reverse().forEach(pair => args.push("-m", pair[1]))
    return args
}
function move(index, direction) {
    var from = keys[index], row = rows[from.row]
    if (direction === "left" || direction === "right") {
        var position = row.indexOf(from) + (direction === "right" ? 1 : -1)
        return row[Math.max(0, Math.min(row.length-1, position))].index
    }
    var target = rows[Math.max(0, Math.min(rows.length-1, from.row + (direction === "down" ? 1 : -1)))]
    var centre = from.column + from.units / 2
    return target.reduce((a,b) => Math.abs(a.column+a.units/2-centre) <= Math.abs(b.column+b.units/2-centre) ? a : b).index
}
function lockAllowed(key, modifiers) {
    return !key.modifier && (modifiers & (control|alt|meta)) === 0
        && (key.text !== undefined || [0,3,4,7,0x10,0x11,0x12,0x14].includes(key.key - 0x01000000))
}
if (typeof module !== "undefined") module.exports = { rows, keys, shift, control, alt, meta, text, action, command, move, lockAllowed }
