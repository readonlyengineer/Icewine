function nextEnabled(entries, current, step) {
    if (entries.length === 0)
        return -1

    const direction = step < 0 ? -1 : 1
    let index = current >= 0 && current < entries.length
        ? current : direction > 0 ? -1 : 0
    for (let i = 0; i < entries.length; i++) {
        index = (index + direction + entries.length) % entries.length
        if (!entries[index].isSeparator && entries[index].enabled)
            return index
    }
    return -1
}

if (typeof module !== "undefined")
    module.exports = { nextEnabled }
