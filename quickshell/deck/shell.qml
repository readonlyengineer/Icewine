import Quickshell
import qs.config as Config
import "adapters" as Adapters
import "modules" as Modules
ShellRoot {
    Modules.Wallpaper {}
    Modules.SessionControl {
        id: session
        authenticationRequired: Config.Settings.authenticationRequired
    }
    Adapters.Hyprland { id: hyprlandAdapter }
    Modules.NotificationService {
        id: notifications
    }
    Modules.NotificationToasts {
        compositor: hyprlandAdapter
        notificationService: notifications
    }
    Modules.Topbar {
        id: topbar
        compositor: hyprlandAdapter
        notificationService: notifications
        radial: deckOverlay
        sessionLocked: session.locked
        fullWidth: true
        excludeSteamApps: true
    }
    Modules.GameLauncher { compositor: hyprlandAdapter }
    DeckOverlay {
        id: deckOverlay
        compositor: hyprlandAdapter
        sessionLocked: session.locked
        shell: topbar
    }
}
