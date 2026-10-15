pragma Singleton
import QtQml
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property var widgetSelections: ({})
    readonly property var widgetPolicy: {
        try { return JSON.parse(Quickshell.env("ICEWINE_WIDGET_POLICY") || "{}") }
        catch (error) { return ({}) }
    }
    readonly property bool notificationToasts: widgetEnabled("notificationToasts")
    readonly property bool windowSwitcher: widgetEnabled("windowSwitcher")

    function widgetEnabled(name) {
        if (typeof widgetPolicy[name] === "boolean") return widgetPolicy[name]
        return typeof widgetSelections[name] === "boolean" ? widgetSelections[name] : true
    }

    property FileView widgetsFile: FileView {
        path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state")
            + "/icewine/widgets.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                const value = JSON.parse(text())
                if (!value || Array.isArray(value) || typeof value !== "object"
                    || Object.keys(value).some(name => !["notificationToasts", "windowSwitcher"].includes(name)
                        || typeof value[name] !== "boolean")) throw new Error("Invalid widget selections")
                root.widgetSelections = value
            } catch (error) { console.warn("Widget preferences unchanged:", error) }
        }
        onLoadFailed: root.widgetSelections = ({})
    }

    readonly property bool authenticationRequired: Quickshell.env("ICEWINE_AUTHENTICATION_REQUIRED") !== "false"
    readonly property int batteryLow: 20
    readonly property int batteryCritical: 10
    readonly property int batteryDanger: 5
    readonly property int batterySleep: 3
}
