function nextIndex(index, count) {
    return count > 0 ? (index + 1) % count : 0
}

function keyboardInset(keyboardHost, screen, visible, height) {
    return visible && keyboardHost === screen ? height : 0
}

function scaleFactor(width, height) {
    return Math.max(0.8, Math.min(1.25, width / 1920, height / 1080))
}

if (typeof module !== "undefined")
    module.exports = { keyboardInset, nextIndex, scaleFactor }
