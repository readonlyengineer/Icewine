function steamUiReady(line) {
    return /^GAMESCOPE_FOCUSED_APP_GFX(?:\([^)]*\))?\s*=\s*769\s*$/.test(String(line).trim())
}

if (typeof module !== "undefined")
    module.exports = { steamUiReady }
