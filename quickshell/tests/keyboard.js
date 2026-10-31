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

// Exercise the real view geometry and reopen/drag handlers without a QML engine.
const viewSource = fs.readFileSync(require('node:path').join(__dirname, '../modules/KeyboardView.qml'), 'utf8')
const geometry = vm.createContext({parent: {width:1280, height:800}, width:1040, height:344,
    x:0, y:0, relativePosition:{x:0.5,y:1}, keyboardDrag:{active:false},
    Qt:{point:(x,y)=>({x,y})}, selected:8, visible:true, cancel(){}, revealSelected(){}})
for (const name of ['place','rememberPosition'])
    vm.runInContext(viewSource.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{[\\s\\S]*?^    \\}', 'm'))[0], geometry)
geometry.root = geometry
geometry.place()
assert.equal(geometry.x,120); assert.equal(geometry.y,444)
geometry.x=60; geometry.y=111; geometry.rememberPosition()
assert.equal(geometry.relativePosition.x,0.25); assert.equal(geometry.relativePosition.y,0.25)
geometry.x=0; geometry.y=0
vm.runInContext(viewSource.match(/    onVisibleChanged: (.+)/)[1], geometry)
assert.equal(geometry.x,60); assert.equal(geometry.y,111)
assert.equal(geometry.selected,0,'reopening still resets key selection')
geometry.parent.width=2560; geometry.parent.height=1440; geometry.place()
assert.equal(geometry.x,380); assert.equal(geometry.y,271,'screen-relative position scales')
geometry.width=3000; geometry.height=1500; geometry.place(); geometry.rememberPosition()
assert.equal(geometry.x,0); assert.equal(geometry.y,0)
assert.equal(geometry.relativePosition.x,0.25,'zero travel preserves saved horizontal fraction')
assert.equal(geometry.relativePosition.y,0.25,'zero travel preserves saved vertical fraction')
geometry.width=1040; geometry.height=344
geometry.x=-100; geometry.y=9999; geometry.rememberPosition(); geometry.place()
assert.equal(geometry.x,0); assert.equal(geometry.y,1084,'remembered positions stay bounded')
geometry.keyboardDrag.active=true; geometry.x=123; geometry.place()
assert.equal(geometry.x,123,'geometry notifications do not overwrite an active drag')
assert(!viewSource.includes('pinControl') && !viewSource.includes('property bool pinned'))
const dragHandler=viewSource.match(/                onActiveChanged: (.+)/)[1]
geometry.keyboardDrag.active=false; geometry.active=false; geometry.x=380; geometry.y=271
vm.runInContext(dragHandler,geometry)
assert.equal(geometry.relativePosition.x,0.25,'drag release remembers actual position')
const color=viewSource.match(/    color: (.+)/)[1]
geometry.Theme={Palette:{backgroundDark:'dark',keyboardOpacity:0.4,alpha:(_,a)=>a}}
assert.equal(vm.runInContext(color,geometry),0.9,'background has a 90% opacity floor')
geometry.Theme.Palette.keyboardOpacity=1
assert.equal(vm.runInContext(color,geometry),1,'opaque themes remain opaque')
console.log('PASS: always-draggable geometry, relative reopen/resize position, bounds and opacity floor')
