const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const K = require('../modules/KeyboardModel.js')
assert.deepEqual(K.rows.map(r=>r.length), [16,15,15,14,14,10])
assert.equal(K.keys.length, 84)
assert.equal(new Set(K.keys.map(k=>k.row+':'+k.column)).size, 84)
assert.deepEqual(K.rows.map(r=>r.reduce((n,k)=>n+k.units,0)), [16,16,16,16,16,16])
const a = K.keys.find(k=>k.text==='a'), one = K.keys.find(k=>k.text==='1')
assert.equal(K.text(a,0,false),'a')
assert.equal(K.text(a,K.shift,false),'A')
assert.equal(K.text(a,0,true),'A')
assert.equal(K.text(a,K.shift,true),'a')
assert.equal(K.text(one,K.shift,true),'!')
assert.deepEqual(K.command(K.action(a,K.control,false)), ['timeout','--kill-after=1s','2s','wtype','-M','ctrl','-k','U0061','-m','ctrl'])
for (const key of K.keys.filter(k=>!k.modifier && !k.caps)) {
    for (const mask of [0,K.shift,K.control|K.alt|K.meta]) {
        const args=K.command(K.action(key,mask,false))
        assert(!args.includes('-P') && !args.includes('-s'), 'finite activations only')
        assert.equal(args.filter(x=>x==='-M').length,args.filter(x=>x==='-m').length)
    }
}
assert(!K.lockAllowed(a,K.control), 'no clipboard/window chords inside lock')
assert(K.lockAllowed(a,K.shift))
assert(!K.lockAllowed(K.keys.find(k=>k.symbol==='Print'),0))
const left=K.keys.find(k=>k.symbol==='Left').index
assert.equal(K.move(K.move(left,'right'),'left'),left)
assert(K.move(a.index,'up')!==a.index)
// Exercise the real QML owner functions, with explicit fake seat/process state.
const source=fs.readFileSync(require('node:path').join(__dirname,'../modules/KeyboardController.qml'),'utf8')
const functionBody=name=>source.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{[\\s\\S]*?^    \\}', 'm'))[0]
const target={address:'0x1'}, replacement={address:'0x1'}
const context=vm.createContext({ Model:K, controllerReady:true, error:"", pending:false, busy:false, desktopVisible:true, destination:target,
    compositor:{toplevels:[target],activeWindowAddress:'0x1'},session:{locked:false}, delivery:{running:false} })
vm.runInContext(functionBody('send'), context)
context.send(K.action(a,0,false)); assert(context.delivery.running)
context.busy=true; context.delivery.running=false; context.send(K.action(one,0,false)); assert(!context.delivery.running, 'busy work is dropped')
context.busy=false; context.session.locked=true; context.send(K.action(a,0,false)); assert(!context.delivery.running,'lock refuses injection')
context.session.locked=false; context.compositor.activeWindowAddress='0x2'; context.send(K.action(a,0,false)); assert(!context.delivery.running)
context.compositor.activeWindowAddress='0x1'; context.compositor.toplevels=[replacement]; context.send(K.action(a,0,false)); assert(!context.delivery.running,'address reuse is not destination identity')
console.log('PASS: 84-key semantics, chords, lock restrictions, navigation and real owner no-backlog/focus guards')
