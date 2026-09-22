function sessionPath(output) {
    const match = /^\(objectpath '(\/org\/freedesktop\/login1\/session\/[A-Za-z0-9_]+)',\)$/.exec(String(output || "").trim())
    return match ? match[1] : ""
}

function logindEvent(line, path) {
    line = String(line || "").trim()
    if (path && line === path + ": org.freedesktop.login1.Session.Lock ()")
        return "lock"
    if (path && line === path + ": org.freedesktop.login1.Session.Unlock ()")
        return "unlock"
    if (line === "/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (false,)")
        return "resume"
    if (line === "/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (true,)")
        return "sleep"
    return ""
}

if (typeof module !== "undefined")
    module.exports = { sessionPath, logindEvent }
