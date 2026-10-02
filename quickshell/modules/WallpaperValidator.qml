import QtQuick
import Quickshell
import "Wallpaper.js" as Wallpaper

Scope {
    Image {
        source: Wallpaper.fileUrl(Quickshell.env("ICEWINE_WALLPAPER_VALIDATE"))
        asynchronous: true
        cache: false

        onStatusChanged: {
            if (status === Image.Ready) {
                console.log("ICEWINE_WALLPAPER_VALID")
                Qt.quit()
            } else if (status === Image.Error) {
                console.log("ICEWINE_WALLPAPER_INVALID")
                Qt.quit()
            }
        }
    }
}
