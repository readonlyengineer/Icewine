import Quickshell
import qs.config as Config
import "adapters" as Adapters
import "modules" as Modules

ShellRoot {
    Modules.ThemeService {}
    Modules.Wallpaper { id: wallpaperOwner }

    Modules.SessionControl {
        id: session
        wallpaper: wallpaperOwner
        authenticationRequired: Config.Settings.authenticationRequired
        keyboardController: keyboard
    }

    Modules.KeyboardController { id: keyboard; compositor: hyprlandAdapter; session: session }
    Adapters.Hyprland {
        id: hyprlandAdapter
        layoutActive: topbar.layoutActive
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
        keyboard: keyboard
        sessionLocked: session.locked
    }

    Modules.GameLauncher {
        compositor: hyprlandAdapter
    }
}
