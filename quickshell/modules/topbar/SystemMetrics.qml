pragma ComponentBehavior: Bound

import QtQuick
import QtQml.Models
import Quickshell
import Quickshell.Io
import Quickshell.Networking

Scope {
    id: root

    property double now: Date.now()
    readonly property alias network: network
    readonly property alias cpu: cpu
    readonly property alias memory: memory
    property var sensorDefinitions: []
    property var sensors: []
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
            for card in /sys/class/drm/card[0-9]*; do
                file="$card/device/gpu_busy_percent"
                [ -r "$file" ] || continue
                printf 'gpu\\t%s\\tGPU %s\\n' "$file" "\${card##*/}"
            done
            for chip in /sys/class/hwmon/hwmon*; do
                file="$chip/temp1_input"
                [ -r "$file" ] || continue
                IFS= read -r name < "$chip/name" || continue
                label=Temperature
                if [ -r "$chip/temp1_label" ]; then
                    IFS= read -r label < "$chip/temp1_label"
                fi
                printf 'temperature\\t%s\\t%s · %s\\n' "$file" "$name" "$label"
            done
            exit 0
        `]
        stdout: StdioCollector {
            onStreamFinished: {
                root.sensorDefinitions = text.trim().split("\n").map(line => line.split("\t"))
                    .filter(fields => fields.length === 3
                        && /^(gpu|temperature)$/.test(fields[0])
                        && /^\/sys\/class\/(drm|hwmon)\//.test(fields[1]))
                    .map(fields => ({ kind: fields[0], path: fields[1], title: fields[2] }))
            }
        }
    }

    Instantiator {
        model: root.sensorDefinitions
        delegate: MetricSampler {
            required property var modelData
            readonly property string title: modelData.title
            clock: root
            path: modelData.path
            kind: modelData.kind
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
