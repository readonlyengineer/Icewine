const assert = require("node:assert/strict")
const Wallpaper = require("../modules/Wallpaper.js")

const dataHome = "/home/alice/Library Pictures"
assert.equal(Wallpaper.fileUrl(dataHome + "/photo #1.png"),
    "file:///home/alice/Library%20Pictures/photo%20%231.png")
assert.equal(Wallpaper.source(dataHome, false, "unused"),
    "file:///home/alice/Library%20Pictures/wallpapers/default.jpg")
assert.equal(Wallpaper.source(dataHome, true, "revision 1"),
    "file:///home/alice/Library%20Pictures/icewine/wallpapers/selection.img?revision=revision%201")

assert.equal(Wallpaper.authSource(dataHome, true, true, "revision 2"),
    "file:///home/alice/Library%20Pictures/icewine/wallpapers/auth.img?revision=revision%202")
assert.equal(Wallpaper.authSource(dataHome, false, true, "revision 2"),
    Wallpaper.source(dataHome, true, "revision 2"))
assert.equal(Wallpaper.authSource(dataHome, false, false, "revision 2"),
    Wallpaper.source(dataHome, false, "revision 2"))
