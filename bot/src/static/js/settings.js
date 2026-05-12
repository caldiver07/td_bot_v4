import * as ui from './ui.js';

export function toggleAutoTrading() {
    const checkbox = document.getElementById('auto-trading');
    const status = document.getElementById('auto-trading-status');
    const newState = checkbox.checked;
    if (newState) {
        status.textContent = 'ON';
        status.className = 'auto-trading-status on';
    } else {
        status.textContent = 'OFF';
        status.className = 'auto-trading-status off';
    }
    ui.updateSettings();
    console.log('Auto Trading:', newState ? 'Enabled' : 'Disabled');
}
export function setAutoTrading(state) {
    const checkbox = document.getElementById('auto-trading');
    checkbox.checked = state;
    toggleAutoTrading();
}

/*order timeout*/
export function saveOrderTimeout() {
    const orderTimeoutInput = document.getElementById('order-timeout');
    localStorage.setItem('order_timeout', orderTimeoutInput.value);
    ui.updateSettings();
}
export function restoreOrderTimeout(){
    const orderTimeoutInput = document.getElementById('order-timeout');
    const orderTimeoutState = localStorage.getItem('order_timeout');
    if (orderTimeoutState !== null) {
        orderTimeoutInput.value = orderTimeoutState;
    }
}


/*opening fill threshold*/
export function saveOpeningFillThreshold() {
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    localStorage.setItem('opening-fill-threshold', openingFillThresholdInput.value);
    ui.updateSettings();
}
export function restoreOpeningFillThreshold(){
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    const openingFillThresholdState = localStorage.getItem('opening-fill-threshold');
    if (openingFillThresholdState !== null) {
        openingFillThresholdInput.value = openingFillThresholdState;
    }
}

/*closing fill threshold*/
export function saveClosingFillThreshold() {
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    localStorage.setItem('closing-fill-threshold', closingFillThresholdInput.value);
    ui.updateSettings();
}
export function restoreClosingFillThreshold(){
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    const closingFillThresholdState = localStorage.getItem('closing-fill-threshold');
    if (closingFillThresholdState !== null) {
        closingFillThresholdInput.value = closingFillThresholdState;
    }
}

/*opening order threshold*/
export function saveOpeningOrderThreshold() {
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');
    localStorage.setItem('opening-order-threshold', openingOrderThresholdInput.value);
    ui.updateSettings();
}
export function restoreOpeningOrderThreshold(){
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');
    const openingOrderThresholdState = localStorage.getItem('opening-order-threshold');
    if (openingOrderThresholdState !== null) {
        openingOrderThresholdInput.value = openingOrderThresholdState;
    }
}

/*paused charts timeout*/
export function savePausedChartsTimeout() {
    const pausedChartsTimeoutInput = document.getElementById('paused-charts-timeout');
    localStorage.setItem('paused-charts-timeout', pausedChartsTimeoutInput.value);
    ui.updateSettings();
}
export function restorePausedChartsTimeout(){
    const pausedChartsTimeoutInput = document.getElementById('paused-charts-timeout');
    const pausedChartsTimeoutState = localStorage.getItem('paused-charts-timeout');
    if (pausedChartsTimeoutState !== null) {
        pausedChartsTimeoutInput.value = pausedChartsTimeoutState;
    }
}

/*stuck-timeout-mult */
export function saveStuckTimeoutMult() {
    const stuckTimeoutMultInput = document.getElementById('stuck-timeout-mult');
    localStorage.setItem('stuck-timeout-mult', stuckTimeoutMultInput.value);
    ui.updateSettings();
}
export function restoreStuckTimeoutMult(){
    const stuckTimeoutMultInput = document.getElementById('stuck-timeout-mult');
    const stuckTimeoutMultState = localStorage.getItem('stuck-timeout-mult');
    if (stuckTimeoutMultState !== null) {
        stuckTimeoutMultInput.value = stuckTimeoutMultState;
    }
}

/*Group order bultiplier*/
export function saveGroupOrderMultiplier() {
    const groupOrderMultiplierInput = document.getElementById('group-order-multiplier');
    localStorage.setItem('group-order-multiplier', groupOrderMultiplierInput.value);
    ui.updateSettings();
}
export function restoreGroupOrderMultiplier(){
    const groupOrderMultiplierInput = document.getElementById('group-order-multiplier');
    const groupOrderMultiplierState = localStorage.getItem('group-order-multiplier');
    if (groupOrderMultiplierState !== null) {
        groupOrderMultiplierInput.value = groupOrderMultiplierState;
    }
}

/*Closing Order Multiplier*/
export function saveClosingOrderMultiplier() {
    const closingOrderMultiplierInput = document.getElementById('closing-order-multiplier');
    localStorage.setItem('closing-order-multiplier', closingOrderMultiplierInput.value);
    ui.updateSettings();
}
export function restoreClosingOrderMultiplier(){
    const closingOrderMultiplierInput = document.getElementById('closing-order-multiplier');
    const closingOrderMultiplierState = localStorage.getItem('closing-order-multiplier');
    if (closingOrderMultiplierState !== null) {
        closingOrderMultiplierInput.value = closingOrderMultiplierState;
    }
}

/*closing timeout*/
export function saveClosingTimeout() {
    const closingTimeoutInput = document.getElementById('closing-timeout');
    localStorage.setItem('closing-timeout', closingTimeoutInput.value);
    ui.updateSettings();
}
export function restoreClosingTimeout(){
    const closingTimeoutInput = document.getElementById('closing-timeout');
    const closingTimeoutState = localStorage.getItem('closing-timeout');
    if (closingTimeoutState !== null) {
        closingTimeoutInput.value = closingTimeoutState;
    }
}

export function exportToWindow() {
    window.toggleAutoTrading = toggleAutoTrading;
    window.saveOrderTimeout = saveOrderTimeout;
    window.saveOpeningFillThreshold = saveOpeningFillThreshold;
    window.saveClosingFillThreshold = saveClosingFillThreshold;
    window.saveOpeningOrderThreshold = saveOpeningOrderThreshold;
    window.savePausedChartsTimeout = savePausedChartsTimeout;
    window.saveStuckTimeoutMult = saveStuckTimeoutMult;
    window.saveGroupOrderMultiplier = saveGroupOrderMultiplier;
    window.saveClosingOrderMultiplier = saveClosingOrderMultiplier;
    window.saveClosingTimeout = saveClosingTimeout;
}
exportToWindow();