// Only user intent lives here. Hover, animation and controller routing are
// separate inputs, never alternative owners of widget lifetime.
function initial(suppressed = false) {
    return { held: null, latched: false, suppressed: suppressed, page: "", engaged: false, screen: "" }
}

function reduce(state, event) {
    switch (event.type) {
    case "press":
        if (state.held) return state
        const toggle = event.behaviour === "toggle" && !event.fullscreen
        return Object.assign({}, state, { held: { screen: event.screen, toggle: toggle }, suppressed: false,
            latched: toggle ? !state.latched : false })
    case "fullscreen":
        return state.held?.toggle && event.screens.includes(state.held.screen)
            ? Object.assign({}, state, { held: { screen: state.held.screen, toggle: false }, latched: false }) : state
    case "release":
        return Object.assign({}, state, { held: null })
    case "open":
        // Returning to this icon must not release its card's keyboard ownership.
        if (state.engaged && !event.engaged && state.page === event.page && state.screen === event.screen)
            return state
        return Object.assign({}, state, {
            suppressed: false, page: event.page, engaged: event.engaged === true, screen: event.screen
        })
    case "engage":
        return state.page ? Object.assign({}, state, { engaged: true }) : state
    case "dismiss":
        return Object.assign({}, state, { page: "", engaged: false, screen: "" })
    case "resume":
        return Object.assign({}, state, { suppressed: false })
    case "hide":
    case "reset":
        return initial(event.type === "hide")
    default:
        return state
    }
}

function barVisible(state, radialVisible, hovered, behaviour) {
    if (state.suppressed && !radialVisible) return false
    return behaviour === "always" || state.latched || (state.held !== null && !state.held.toggle)
        || radialVisible || (state.page !== "" && state.page !== "switcher") || hovered
}

if (typeof module !== "undefined")
    module.exports = { initial, reduce, barVisible }
