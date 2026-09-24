pragma ComponentBehavior: Bound

import QtQuick
import QtQml.Models
import Quickshell
import Quickshell.Io
import Quickshell.Networking
import "Metrics.js" as Metrics

Scope {
    id: root

    property double now: Date.now()
    readonly property alias network: network
    readonly property alias cpu: cpu
    readonly property alias memory: memory
    property var sensorDefinitions: []
    property var sensors: []
    readonly property var cpuTemperature: sensors.find(sensor => sensor.role === "cpu") ?? null
    readonly property var gpus: Metrics.gpuGroups(sensors)
    signal tick()

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            root.now = Date.now()
            root.tick()
        }
    }

    MetricSampler {
        id: cpu
        clock: root
        path: "/proc/stat"
        kind: "cpu"
    }

    MetricSampler {
        id: memory
        clock: root
        path: "/proc/meminfo"
        kind: "memory"
    }

    // Ponytail: discover once at startup; use directory watching if hot-plug
    // sensors must appear without restarting the shell.
    Process {
        running: true
        command: ["sh", "-c", `
            for chip in /sys/class/hwmon/hwmon*; do
                [ -r "$chip/name" ] || continue
                IFS= read -r name < "$chip/name" || continue
                for file in "$chip"/temp*_input; do
                    [ -r "$file" ] || continue
                    label_file="\${file%_input}_label"
                    [ -r "$label_file" ] || continue
                    IFS= read -r label < "$label_file" || continue
                    printf 'temperature\\t%s\\tcpu\\tcpu\\t%s\\t%s\\n' "$file" "$name" "$label"
                done
            done
            seen='|'
            for card in /sys/class/drm/card[0-9]*; do
                device=$(readlink -f "$card/device") || continue
                key="\${device##*/}"
                case "$seen" in *"|$device|"*) continue;; esac
                seen="$seen$device|"
                file="$card/device/gpu_busy_percent"
                [ ! -r "$file" ] || printf 'usage\\t%s\\tgpu\\t%s\\tdrm\\tUsage\\n' "$file" "$key"
                for chip in "$card/device"/hwmon/hwmon*; do
                    [ -r "$chip/name" ] || continue
                    IFS= read -r name < "$chip/name" || continue
                    for file in "$chip"/temp*_input; do
                        [ -r "$file" ] || continue
                        label_file="\${file%_input}_label"
                        [ -r "$label_file" ] || continue
                        IFS= read -r label < "$label_file" || continue
                        printf 'temperature\\t%s\\tgpu\\t%s\\t%s\\t%s\\n' "$file" "$key" "$name" "$label"
                    done
                done
            done
            exit 0
        `]
        stdout: StdioCollector {
            onStreamFinished: {
                root.sensorDefinitions = Metrics.sensorDefinitions(text)
            }
        }
    }

    Instantiator {
        model: root.sensorDefinitions
        delegate: MetricSampler {
            required property var modelData
            readonly property string title: modelData.title
            readonly property string role: modelData.role
            readonly property string device: modelData.device
            readonly property string label: modelData.label
            clock: root
            path: modelData.path
            kind: modelData.kind === "usage" ? "gpu" : modelData.kind
        }
        onObjectAdded: (index, object) => root.sensors = root.sensors.concat([object])
        onObjectRemoved: (index, object) => root.sensors = root.sensors.filter(sensor => sensor !== object)
    }

    MetricSampler {
        id: network
        clock: root
        path: "/proc/net/dev"
        kind: "network"
        interfaces: Networking.devices.values.filter(device =>
            device.type === DeviceType.Wifi || device.type === DeviceType.Wired).map(device => device.name)
    }
}
