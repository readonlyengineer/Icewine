function nextIndex(index, count) {
    return count > 0 ? (index + 1) % count : 0
}

function keyboardInset(keyboardHost, screen, visible, height) {
    return visible && keyboardHost === screen ? height : 0
}

function submission(available, inactive, authenticating, password, user) {
    if (!available || !password)
        return null
    if (inactive)
        return { action: "create", response: password, user }
    if (authenticating)
        return { action: "respond", response: password }
    return null
}

function authenticationMessage(pendingResponse, message, error, responseRequired, echoResponse) {
    const response = responseRequired ? pendingResponse : ""
    return {
        prompt: message || "Password",
        message: error ? message : "",
        failed: error,
        secretInput: !echoResponse,
        busy: !responseRequired || response !== "",
        pendingResponse: response ? "" : pendingResponse,
        response
    }
}

function authenticationFailure(message) {
    return {
        prompt: "Password",
        message: message || "Access denied",
        failed: true,
        secretInput: true,
        busy: false,
        pendingResponse: ""
    }
}

function sessionCommand(prefix, sessions, index) {
    if (!sessions || index < 0 || index >= sessions.length)
        return null
    return Array.from(prefix || []).concat([sessions[index] + ".desktop"])
}

function scaleFactor(width, height) {
    return Math.min(width / 1920, height / 1080)
}

if (typeof module !== "undefined")
    module.exports = {
        authenticationFailure, authenticationMessage, keyboardInset, nextIndex,
        scaleFactor, sessionCommand, submission
    }
