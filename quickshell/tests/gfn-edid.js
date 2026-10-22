const assert = require('node:assert/strict')
const {gfnEdid} = require('../modules/GameLauncher.js')
function block(bytes) {
    const result = new Uint8Array(128)
    result.set(bytes)
    result[127] = -result.reduce((sum, byte) => sum + byte, 0) & 255
    return Array.from(result)
}
const base = block([0, 255, 255, 255, 255, 255, 255, 0,
    ...Array(46).fill(0), ...Array.from({length: 18}, (_, i) => i), ...Array(54).fill(0), 1])
const payload = [0xe3, 5, 0x80, 0, 0xe6, 6, 5, 1, 0x74, 0x60, 2]
const displayId = (data, padding = 0) => block([0x70, 0x20, 3 + data.length + padding,
    0, 0, 0x81, 0, data.length, ...data])
const hex = bytes => Buffer.from(bytes).toString('hex')
const convert = bytes => Array.from(Buffer.from(gfnEdid(hex(bytes)), 'hex'))
const panel = base.concat(displayId(payload))
const standard = base.concat(block([2, 3, 4 + payload.length, 0, ...payload]))
const compatible = convert(panel)
assert.equal(compatible.length, 384)
assert.deepEqual(compatible.slice(256), panel.slice(128), 'Original extensions survive')
assert.deepEqual(compatible.slice(54, 72), panel.slice(54, 72), 'Panel timings survive')
assert.deepEqual(compatible.slice(132, 132 + payload.length), payload, 'Copy actual colour/luminance metadata')
for (let i = 0; i < compatible.length; i += 128)
    assert.equal(compatible.slice(i, i + 128).reduce((sum, byte) => sum + byte, 0) % 256, 0)
const padded = base.concat(displayId(payload, 2))
assert.deepEqual(convert(padded).slice(256), padded.slice(128), 'DisplayID allows trailing zero padding')
assert.deepEqual(convert(standard), standard, 'Standard PQ HDR EDID passes unchanged')
const changedPayload = payload.map((byte, i) => i === 8 ? 0x52 : byte)
assert.deepEqual(convert(base.concat(displayId(changedPayload))).slice(132, 143), changedPayload,
    'Another display retains its own luminance')
for (const invalid of [[], panel.slice(0, -1), panel.concat(0), Array(256).fill(0),
    panel.map((byte, i) => i === 60 ? byte ^ 1 : byte), block(base.slice(0, 126)),
    base.concat(block([0x70, 0x20, 127, 0, 0])),
    base.concat(block([0x70, 0x20, 3, 0, 0, 0x81, 0, 30])),
    base.concat(block([0x70, 0x20, 2, 0, 0, 0x81, 0])),
    base.concat(block([2, 3, 5, 0, 0xe6])),
    base.concat(displayId(payload.concat(payload))),
    base.concat(displayId([0, ...payload])),
    base.concat(displayId(payload.map((byte, i) => i === 6 ? 1 : byte)))])
    assert.throws(() => convert(invalid), 'Malformed, ambiguous and SDR EDID must not enable HDR')
const unknownRevision = displayId(payload).slice(0, 127)
unknownRevision[6] = 1
assert.throws(() => convert(base.concat(block(unknownRevision))), /Unsupported embedded CTA revision/)
for (const value of ['', 'zz'.repeat(128), '0'.repeat(255), null])
    assert.throws(() => gfnEdid(value))
// A standard HDR extension must not hide a corrupt later extension.
const two = block([...base.slice(0, 126), 2]).concat(standard.slice(128), displayId(payload))
two[two.length - 1] ^= 1
assert.throws(() => convert(two))
console.log('GFN EDID metadata preservation, passthrough and fail-closed checks passed')

// Exercise the actual lifetime adapter with disposable Flatpak/Gamescope peers.
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const {spawn, spawnSync} = require('node:child_process')
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'gfn-launcher-'))
function mock(name, code) {
    const file = path.join(directory, name)
    fs.writeFileSync(file, `#!${process.execPath}\n${code}`)
    fs.chmodSync(file, 0o755)
}
mock('notify-send', `require('fs').writeFileSync(process.env.TEST_ROOT + '/notification', JSON.stringify(process.argv.slice(2)))`)
mock('gamescope', `
const fs = require('fs'), args = process.argv.slice(2)
fs.writeFileSync(process.env.TEST_ROOT + '/gamescope.json', JSON.stringify(args))
const split = args.indexOf('--')
const result = require('child_process').spawnSync(args[split + 1], args.slice(split + 2), {stdio: 'inherit'})
process.exit(result.status ?? 1)
`)
mock('flatpak', `
const fs = require('fs'), args = process.argv.slice(2), root = process.env.TEST_ROOT
if (args[0] === 'ps') { console.log(process.env.TEST_RUNNING || ''); process.exit(0) }
if (args.includes('--command=sh')) {
    if (!args.includes('--env=ENABLE_GAMESCOPE_WSI=1') || !args.includes('--unset-env=DISABLE_GAMESCOPE_WSI')) process.exit(2)
    process.exit(process.env.TEST_LAYER === 'missing' ? 1 : 0)
}
// Simulate persistent per-app overrides, then apply this invocation's flags.
const env = {DISABLE_GAMESCOPE_WSI: '0', GAMESCOPE_PATCHED_EDID_FILE: '/stale/edid', ...process.env}
for (const arg of args) {
    if (arg.startsWith('--env=')) { const pair = arg.slice(6).split('='); env[pair.shift()] = pair.join('=') }
    if (arg.startsWith('--unset-env=')) delete env[arg.slice(12)]
}
const edid = env.GAMESCOPE_PATCHED_EDID_FILE
if (edid) {
    if (fs.readFileSync(edid).toString('hex') !== process.env.TEST_EDID) process.exit(3)
    if ((fs.statSync(require('path').dirname(edid)).mode & 0o777) !== 0o700) process.exit(4)
}
fs.writeFileSync(root + '/flatpak.json', JSON.stringify({args, env, edid}))
if (process.env.TEST_HOLD === '1') {
    while (!fs.existsSync(root + '/release')) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10)
    if (!fs.existsSync(edid)) process.exit(5)
}
process.exit(Number(process.env.TEST_EXIT || 0))
`)
const adapter = path.join(__dirname, '../tools/geforce-now')
const geometry = ['--backend', 'wayland', '-W', '2880', '-H', '1800', '-w', '2880', '-h', '1800', '-r', '120', '-f', '--expose-wayland']
const env = {...process.env, PATH: directory + path.delimiter + process.env.PATH,
    XDG_RUNTIME_DIR: directory, TEST_ROOT: directory, TEST_EDID: hex(compatible),
    ENABLE_GAMESCOPE_WSI: '1', DISABLE_GAMESCOPE_WSI: '0', GAMESCOPE_PATCHED_EDID_FILE: '/stale/edid'}
const read = file => JSON.parse(fs.readFileSync(path.join(directory, file), 'utf8'))
function run(edid, extra = {}) {
    return spawnSync('bash', [adapter, edid, ...geometry], {env: {...env, ...extra}, encoding: 'utf8', timeout: 5000})
}
async function checkAdapter() {
    let heldChild, heldFinished
    try {
        let result = run(hex(compatible))
        assert.equal(result.status, 0, result.stderr)
        let flatpak = read('flatpak.json'), gamescope = read('gamescope.json')
        assert.deepEqual(gamescope.slice(0, geometry.length), geometry)
        assert(gamescope.includes('--hdr-enabled'))
        assert(!gamescope.includes('--force-windows-fullscreen'))
        assert.equal(flatpak.env.ENABLE_GAMESCOPE_WSI, '1')
        assert.equal(flatpak.env.DISABLE_GAMESCOPE_WSI, undefined, "Even persistent DISABLE=0 must be removed")
        assert.equal(flatpak.env.SDL_VIDEODRIVER, 'x11')
        assert.equal(flatpak.env.WAYLAND_DISPLAY, undefined)
        assert.equal(flatpak.env.vk_wsi_force_swapchain_to_current_extent, 'true')
        assert(flatpak.args.includes('--nosocket=wayland'))
        assert(flatpak.args.includes('--filesystem=' + path.dirname(flatpak.edid) + ':ro'))
        assert(!fs.existsSync(flatpak.edid), 'EDID cleaned up after child exit')
        for (const [edid, extra] of [['', {}], ['malformed', {}], [hex(compatible), {TEST_LAYER: 'missing'}]]) {
            result = run(edid, extra)
            assert.equal(result.status, 0, result.stderr)
            flatpak = read('flatpak.json')
            assert(!read('gamescope.json').includes('--hdr-enabled'))
            assert.equal(flatpak.env.DISABLE_GAMESCOPE_WSI, '1')
            assert.equal(flatpak.env.ENABLE_GAMESCOPE_WSI, undefined)
            assert.equal(flatpak.env.GAMESCOPE_PATCHED_EDID_FILE, undefined)
            assert(!flatpak.args.some(arg => /nosocket|SDL_VIDEODRIVER|filesystem/.test(arg)))
        }
        fs.rmSync(path.join(directory, 'gamescope.json'))
        result = run(hex(compatible), {TEST_RUNNING: 'other.app\ncom.nvidia.geforcenow'})
        assert.equal(result.status, 1)
        assert(!fs.existsSync(path.join(directory, 'gamescope.json')), 'Existing outer app cannot receive a new launch')
        assert(fs.existsSync(path.join(directory, 'notification')))
        result = run(hex(compatible), {TEST_EXIT: '7'})
        assert.equal(result.status, 7)
        assert(!fs.existsSync(read('flatpak.json').edid), 'Failed child also cleans EDID')
        fs.rmSync(path.join(directory, 'flatpak.json'))
        const child = heldChild = spawn('bash', [adapter, hex(compatible), ...geometry], {env: {...env, TEST_HOLD: '1'}, timeout: 10000})
        const finished = heldFinished = new Promise((resolve, reject) => { child.on('exit', resolve); child.on('error', reject) })
        for (let count = 0; !fs.existsSync(path.join(directory, 'flatpak.json')); count++) {
            assert(count < 500, 'Adapter child startup timed out')
            await new Promise(resolve => setTimeout(resolve, 10))
        }
        const temporaryEdid = read('flatpak.json').edid
        assert(fs.existsSync(temporaryEdid), 'EDID survives while child runs')
        result = run(hex(compatible))
        assert.equal(result.status, 1, 'Lifetime lock closes the Flatpak startup race')
        fs.writeFileSync(path.join(directory, 'release'), '')
        assert.equal(await finished, 0)
        assert(!fs.existsSync(temporaryEdid))
        console.log('GFN HDR/SDR invocation, duplicate prevention and EDID lifetime checks passed')
    } finally {
        if (heldChild && heldChild.exitCode === null) {
            fs.writeFileSync(path.join(directory, 'release'), '')
            await heldFinished
        }
        fs.rmSync(directory, {recursive: true, force: true})
    }
}
checkAdapter().catch(error => { console.error(error); process.exitCode = 1 })
