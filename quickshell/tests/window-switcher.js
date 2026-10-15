// Run: node quickshell/tests/window-switcher.js
const assert = require('node:assert/strict')
const Model = require('../modules/WindowSwitcherModel.js')
const window = (address, id, monitor = 'DP-1') => ({address, workspace: {id, name: String(id), monitor: {name: monitor}}})
const a = window('0x1', 1), b = window('0x2', 1), c = window('0x3', 1), d = window('0x4', 3)
const windows = [d, c, window('0x9', -1), window('0x8', 2, 'DP-2'), a, b]
let rows = Model.rows(windows, 'DP-1')
assert.deepEqual(rows.map(row => [row.id, row.windows.map(w => w.address)]), [[1, ['0x1', '0x2', '0x3']], [3, ['0x4']]])
assert.equal(Model.reconcile(rows, null, b.address), b)
assert.equal(Model.move(rows, c, 0, 1), d)
assert.equal(Model.move(rows, d, 0, -1), a)
assert.equal(Model.move(rows, a, -1, 0), a)
assert.equal(Model.move(rows, c, 1, 0), c)
c.workspace = {id: 3, monitor: {name: 'DP-1'}}
rows = Model.rows(windows, 'DP-1')
assert.equal(Model.reconcile(rows, c, ''), c, 'Moved native object retains selection')
const replacement = window(c.address, 3)
rows = Model.rows([a, replacement], 'DP-1')
assert.equal(Model.locate(rows, c), null, 'Address reuse must not validate a closed object')
assert.equal(Model.reconcile([], c, ''), null)
console.log('window switcher grouping, monitor/special filters, navigation and identity pass')

const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm')
const adapter = fs.readFileSync(path.join(__dirname, '../adapters/Hyprland.qml'), 'utf8')
const order = []
const native = {workspace: {activate: () => order.push('workspace')}, wayland: {activate: () => order.push('window')}}
const hyprland = {toplevels: {values: [native]}}
const activate = vm.runInNewContext(adapter.match(/    function activateToplevel\(window\) \{[\s\S]*?^    \}/m)[0] + '; activateToplevel', {Hyprland: hyprland})
activate(native)
assert.deepEqual(order, ['workspace', 'window'])
hyprland.toplevels.values = []
activate(native)
assert.equal(order.length, 2, 'Adapter rejects a stale native object at the final boundary')
