function fileUrl(path) {
    return "file://" + path.split("/").map(segment => encodeURIComponent(segment)).join("/")
}

function source(dataHome, selected, revision) {
    const path = selected
        ? dataHome + "/icewine/wallpapers/selection.img"
        : dataHome + "/wallpapers/default.jpg"
    return fileUrl(path) + (selected ? "?revision=" + encodeURIComponent(revision) : "")
}

function authSource(dataHome, overrideAvailable, selected, revision) {
    return overrideAvailable
        ? fileUrl(dataHome + "/icewine/wallpapers/auth.img") + "?revision=" + encodeURIComponent(revision)
        : source(dataHome, selected, revision)
}

if (typeof module !== "undefined") module.exports = { fileUrl, source, authSource }
