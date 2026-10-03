pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    property var snapshot: ({})
    readonly property bool dark: snapshot.dark !== false
    readonly property bool animate: Quickshell.env("ICEWINE_THEME_TRANSITION") !== "off"

    property color background: "#" + (snapshot.background || "1a1b26")
    property color backgroundDark: "#" + (snapshot.backgroundDark || "16161e")
    property color surface: "#" + (snapshot.surface || "292e42")
    property color selection: "#" + (snapshot.selection || "283457")
    property color border: "#" + (snapshot.border || "3b4261")
    property color foreground: "#" + (snapshot.foreground || "c0caf5")
    property color foregroundDark: "#" + (snapshot.foregroundDark || "a9b1d6")
    property color muted: "#" + (snapshot.muted || "565f89")
    property color primary: "#" + (snapshot.primary || "7aa2f7")
    property color primaryDark: "#" + (snapshot.primaryDark || "3d59a1")
    property color secondary: "#" + (snapshot.secondary || "bb9af7")
    property color tertiary: "#" + (snapshot.tertiary || "73daca")
    property color success: "#" + (snapshot.success || "9ece6a")
    property color warning: "#" + (snapshot.warning || "ff9e64")
    property color caution: "#" + (snapshot.caution || "e0af68")
    property color error: "#" + (snapshot.error || "f7768e")
    property color info: "#" + (snapshot.info || "7dcfff")

    Behavior on background { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on backgroundDark { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on surface { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on selection { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on border { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on foreground { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on foregroundDark { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on muted { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on primary { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on primaryDark { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on secondary { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on tertiary { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on success { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on warning { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on caution { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on error { ColorAnimation { duration: root.animate ? 180 : 0 } }
    Behavior on info { ColorAnimation { duration: root.animate ? 180 : 0 } }

    property FileView file: FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config")
              + "/icewine/current/palette.json"
        blockAllReads: true
    }

    function refresh(): bool {
        try {
            file.reload()
            const next = JSON.parse(file.text())
            for (const key of ["background", "backgroundDark", "surface", "selection", "border",
                               "foreground", "foregroundDark", "muted", "primary", "primaryDark",
                               "secondary", "tertiary", "success", "warning", "caution", "error", "info"])
                if (typeof next[key] !== "string" || !/^[0-9a-fA-F]{6}$/.test(next[key]))
                    return false
            if (typeof next.themeId !== "string" || typeof next.dark !== "boolean")
                return false
            snapshot = next
            return true
        } catch (error) {
            console.warn("Icewine palette was not loaded:", error)
            return false
        }
    }

    Component.onCompleted: refresh()

    function alpha(colour, opacity) {
        return Qt.rgba(colour.r, colour.g, colour.b, opacity)
    }
}
