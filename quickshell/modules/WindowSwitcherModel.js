// Keep native objects throughout selection and activation, never an array index or address alone.
function rows(windows, monitorName) {
    const grouped = new Map()
    for (const window of windows) {
        const workspace = window.workspace
        if (!workspace || workspace.id <= 0 || workspace.monitor?.name !== monitorName)
            continue
        if (!grouped.has(workspace.id))
            grouped.set(workspace.id, { id: workspace.id, name: workspace.name, windows: [] })
        grouped.get(workspace.id).windows.push(window)
    }
    return Array.from(grouped.values()).sort((a, b) => a.id - b.id).map(row => {
        row.windows.sort((a, b) => a.address < b.address ? -1 : a.address > b.address ? 1 : 0)
        return row
    })
}

function locate(rows, window) {
    for (let row = 0; row < rows.length; ++row) {
        const column = rows[row].windows.indexOf(window)
        if (column >= 0) return { row, column }
    }
    return null
}

function reconcile(rows, selected, activeAddress) {
    if (locate(rows, selected)) return selected
    const windows = [].concat(...rows.map(row => row.windows))
    return windows.find(window => window.address === activeAddress) ?? windows[0] ?? null
}

function move(rows, selected, horizontal, vertical) {
    const position = locate(rows, selected)
    if (!position) return reconcile(rows, null, "")
    const row = Math.max(0, Math.min(rows.length - 1, position.row + vertical))
    const column = Math.max(0, Math.min(rows[row].windows.length - 1, position.column + horizontal))
    return rows[row].windows[column]
}

if (typeof module !== "undefined") module.exports = { rows, locate, reconcile, move }
