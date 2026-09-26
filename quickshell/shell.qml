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

    Adapters.Hyprland {
        id: compositor
    }

    Modules.NotificationService {
        id: notifications
    }

    Modules.NotificationToasts {
        compositor: compositor
        notificationService: notifications
    }

    Modules.Topbar {
        id: topbar
        compositor: compositor
        notificationService: notifications
        session: session
        sessionLocked: session.locked
    }

    Modules.GameLauncher {
        compositor: compositor
    }
}
