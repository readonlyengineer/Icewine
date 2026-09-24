import Quickshell
import Quickshell.Io
import qs.config as Config
import "adapters" as Adapters
import "modules" as Modules

ShellRoot {
    Process { id: stopStartupSplash }

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
        sessionLocked: session.locked
        onRendered: stopStartupSplash.exec(["systemctl", "--user", "stop", "icewine-session-splash.service"])
    }

    Modules.GameLauncher {
        compositor: compositor
    }
}
