function fileUrl(path) {
    return "file://" + path.split("/").map(segment => encodeURIComponent(segment)).join("/")
}

function source(dataHome, selected, revision) {
    const path = selected
        ? dataHome + "/icewine/wallpapers/selection.img"
        : dataHome + "/wallpapers/default.jpg"
    return fileUrl(path) + (selected ? "?revision=" + encodeURIComponent(revision) : "")
}

if (typeof module !== "undefined") module.exports = { fileUrl, source }
