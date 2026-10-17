import Quickshell
import qs.config as Config
import "adapters" as Adapters
import "modules" as Modules
import "deck" as Deck
ShellRoot {
    Modules.ThemeService {}
    Modules.Wallpaper { id: wallpaperOwner }
    Modules.SessionControl {
        id: session
        wallpaper: wallpaperOwner
        authenticationRequired: Config.Settings.authenticationRequired
        keyboardController: keyboard
    }
    Modules.KeyboardController {
        id: keyboard
        compositor: hyprlandAdapter
        session: session
        controllerReady: deckOverlay.captured && deckOverlay.keyboardReady
        controllerError: deckOverlay.inputError
    }
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
        radial: deckOverlay
        sessionLocked: session.locked
        fullWidth: true
        excludeSteamApps: true
        layoutsEnabled: false
        onRendered: gameLauncher.autostartSteamGamescope()
    }
    Modules.GameLauncher {
        id: gameLauncher
        compositor: hyprlandAdapter
        handheld: true
    }
    Deck.DeckOverlay {
        id: deckOverlay
        compositor: hyprlandAdapter
        sessionLocked: session.locked
        shell: topbar
        keyboard: keyboard
    }
}
