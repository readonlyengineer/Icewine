const assert = require("node:assert/strict")
const screenshot = require("../modules/topbar/popouts/ScreenshotModel.js")

assert.deepEqual(screenshot.windows([
    { lastIpcObject: { stableId: "first", title: "Editor", class: "code" } },
    { wayland: { appId: "org.example.App", title: "Fallback" }, lastIpcObject: { stableId: "second" } },
    { lastIpcObject: { title: "Unexportable", class: "hidden" } }
]), [
    { stableId: "first", title: "Editor", subtitle: "code" },
    { stableId: "second", title: "Fallback", subtitle: "org.example.App" }
])

console.log("screenshot menu checks passed")
