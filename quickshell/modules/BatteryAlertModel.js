function initial() {
    return { armed: [true, true, true], sleepArmed: true, sleepPending: false }
}

function validPolicy(policy) {
    if (!Array.isArray(policy?.warnings) || policy.warnings.length !== 3)
        return false
    const [low, critical, danger] = policy.warnings
    return [low, critical, danger, policy.sleep].every(Number.isInteger)
        && low <= 100 && low > critical && critical > danger
        && danger > policy.sleep && policy.sleep >= 0
}

function validSample(sample) {
    return sample?.present && Number.isFinite(sample.percentage)
        && sample.percentage >= 0 && sample.percentage <= 100
}

function update(state, sample, policy, enabled) {
    const next = { armed: [...state.armed], sleepArmed: state.sleepArmed,
        sleepPending: state.sleepPending }
    const result = { state: next, alert: null, startSleep: false, cancelSleep: false }
    if (!enabled || !validPolicy(policy) || !validSample(sample)) {
        result.cancelSleep = next.sleepPending
        next.sleepPending = false
        return result
    }

    const percent = sample.percentage
    for (let i = 0; i < policy.warnings.length; ++i)
        if (percent >= policy.warnings[i] + 3)
            next.armed[i] = true
    if (percent >= policy.sleep + 3)
        next.sleepArmed = true
    if (!sample.discharging || percent > policy.sleep) {
        result.cancelSleep = next.sleepPending
        next.sleepPending = false
    }
    if (!sample.discharging)
        return result

    for (let i = policy.warnings.length - 1; i >= 0; --i) {
        if (percent <= policy.warnings[i] && next.armed[i]) {
            result.alert = policy.warnings[i]
            for (let j = 0; j <= i; ++j)
                next.armed[j] = false
            break
        }
    }
    if (percent <= policy.sleep && next.sleepArmed && !next.sleepPending) {
        next.sleepPending = true
        result.startSleep = true
    }
    return result
}

function confirmSleep(state, sample, policy, enabled) {
    const next = { armed: [...state.armed], sleepArmed: state.sleepArmed,
        sleepPending: false }
    const dispatch = state.sleepPending && enabled && validPolicy(policy)
        && validSample(sample) && sample.discharging
        && sample.percentage <= policy.sleep
    if (dispatch)
        next.sleepArmed = false
    return { state: next, dispatch }
}

if (typeof module !== "undefined")
    module.exports = { initial, validPolicy, update, confirmSleep }
