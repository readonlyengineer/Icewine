.import "topbar/CardModules.js" as Cards

// Only user intent lives here. Hover, animation and controller routing are
// separate inputs, never alternative owners of widget lifetime.
function initial() {
    return { held: false, page: "", engaged: false, screen: "" }
}

function reduce(state, event) {
    switch (event.type) {
    case "press":
        return Object.assign({}, state, { held: true })
    case "release":
        return Object.assign({}, state, { held: false })
    case "open":
        if (event.page !== "switcher" && !Cards.modules.includes(event.page))
            return state
        // Hover can leave the window overview, but cannot replace an engaged popout.
        if (state.engaged && state.page !== "switcher" && !event.engaged)
            return state
        return Object.assign({}, state, {
            page: event.page, engaged: event.engaged === true, screen: event.screen
        })
    case "engage":
        return state.page ? Object.assign({}, state, { engaged: true }) : state
    case "dismiss":
        return Object.assign({}, state, { page: "", engaged: false, screen: "" })
    case "reset":
        return initial()
    default:
        return state
    }
}

function barVisible(state, radialVisible, hovered) {
    return state.held || radialVisible || state.page !== "" || hovered
}

if (typeof module !== "undefined")
    module.exports = { initial, reduce, barVisible }
