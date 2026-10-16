import Quickshell
import qs.config as Config
import "adapters" as Adapters
import "modules" as Modules

ShellRoot {
    Modules.ThemeService {}
    Modules.Wallpaper {}

    Modules.SessionControl {
        id: session
        authenticationRequired: Config.Settings.authenticationRequired
    }

    Adapters.Hyprland {
        id: hyprlandAdapter
        layoutActive: topbar.layoutsEnabled && !session.locked && topbar.ui.page === "layout"
    }

    Modules.NotificationService {
        id: notifications
    }
    Modules.BatteryAlert { session: session }

    LazyLoader {
        active: Config.Settings.notificationToasts
        component: Modules.NotificationToasts {
            compositor: hyprlandAdapter
            notificationService: notifications
        }
    }

    Modules.Topbar {
        id: topbar
        compositor: hyprlandAdapter
        notificationService: notifications
        session: session
        sessionLocked: session.locked
    }

    Modules.GameLauncher {
        compositor: hyprlandAdapter
    }
}
