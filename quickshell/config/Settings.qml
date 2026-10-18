pragma Singleton
import QtQml
import Quickshell
import Quickshell.Io
import "../icewine/modules/topbar/CardModules.js" as Cards

QtObject {
    id: root
    property var widgetSelections: ({})
    readonly property var widgetPolicy: {
        try { return JSON.parse(Quickshell.env("ICEWINE_WIDGET_POLICY") || "{}") }
        catch (error) { return ({}) }
    }
    readonly property bool notificationToasts: widgetEnabled("notificationToasts")
    readonly property bool windowSwitcher: widgetEnabled("windowSwitcher")

    readonly property string barBehaviour: barChoice("barBehaviour", Cards.barBehaviours, "keyboard")
    readonly property string barLocation: barChoice("barLocation", Cards.barLocations, "above")

    readonly property string barStyle: barChoice("barStyle", Cards.barStyles, "anchored")
    readonly property int barWidth: {
        const policy = widgetPolicy.barWidth
        if (policy !== undefined && policy !== null)
            return Cards.validBarWidth(policy) ? policy : 80
        return widgetSelections.barWidth ?? 80
    }

    function barChoice(name, choices, fallback) {
        const policy = widgetPolicy[name]
        if (policy !== undefined && policy !== null)
            return choices.includes(policy) ? policy : fallback
        return widgetSelections[name] ?? fallback
    }

    readonly property var cardStacks: {
        if (widgetPolicy.cardStacks !== undefined && widgetPolicy.cardStacks !== null) {
            try { return Cards.validate(widgetPolicy.cardStacks) }
            catch (error) { console.warn("Invalid card stack policy:", error); return Cards.defaults }
        }
        return widgetSelections.cardStacks ?? Cards.defaults
    }

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
                root.widgetSelections = Cards.preferences(value)
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
