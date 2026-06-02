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

export function toggleAlgoVwap() {
    const checkbox = document.getElementById('algo-vwap');
    localStorage.setItem('v4_algo_vwap_enabled', checkbox.checked);
    ui.updateSettings();
}

export function toggleAlgoScalp() {
    const checkbox = document.getElementById('algo-scalp');
    localStorage.setItem('v4_algo_scalp_enabled', checkbox.checked);
    ui.updateSettings();
}

export function toggleAlgoFlat() {
    const checkbox = document.getElementById('algo-flat');
    localStorage.setItem('v4_algo_flat_enabled', checkbox.checked);
    ui.updateSettings();
}

export function restoreAlgoSettings() {
    const vwapCheckbox = document.getElementById('algo-vwap');
    const scalpCheckbox = document.getElementById('algo-scalp');
    const flatCheckbox = document.getElementById('algo-flat');
    
    if(vwapCheckbox) {
        let vwapState = localStorage.getItem('v4_algo_vwap_enabled');
        if (vwapState !== null) {
            vwapCheckbox.checked = (vwapState === 'true');
        }
    }
    
    if(scalpCheckbox) {
        let scalpState = localStorage.getItem('v4_algo_scalp_enabled');
        if (scalpState !== null) {
            scalpCheckbox.checked = (scalpState === 'true');
        }
    }
    
    if(flatCheckbox) {
        let flatState = localStorage.getItem('v4_algo_flat_enabled');
        if (flatState !== null) {
            flatCheckbox.checked = (flatState === 'true');
        }
    }
}

/*order timeout*/
export function saveOrderTimeout() {
    const orderTimeoutInput = document.getElementById('order-timeout');
    localStorage.setItem('v4_order_timeout', orderTimeoutInput.value);
    ui.updateSettings();
}
export function restoreOrderTimeout(){
    const orderTimeoutInput = document.getElementById('order-timeout');
    const orderTimeoutState = localStorage.getItem('v4_order_timeout');
    if (orderTimeoutState !== null) {
        orderTimeoutInput.value = orderTimeoutState;
    }
}


/*opening fill threshold*/
export function saveOpeningFillThreshold() {
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    localStorage.setItem('v4_opening-fill-threshold', openingFillThresholdInput.value);
    ui.updateSettings();
}
export function restoreOpeningFillThreshold(){
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    const openingFillThresholdState = localStorage.getItem('v4_opening-fill-threshold');
    if (openingFillThresholdState !== null) {
        openingFillThresholdInput.value = openingFillThresholdState;
    }
}

/*closing fill threshold*/
export function saveClosingFillThreshold() {
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    localStorage.setItem('v4_closing-fill-threshold', closingFillThresholdInput.value);
    ui.updateSettings();
}
export function restoreClosingFillThreshold(){
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    const closingFillThresholdState = localStorage.getItem('v4_closing-fill-threshold');
    if (closingFillThresholdState !== null) {
        closingFillThresholdInput.value = closingFillThresholdState;
    }
}

/*opening order threshold*/
export function saveOpeningOrderThreshold() {
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');
    localStorage.setItem('v4_opening-order-threshold', openingOrderThresholdInput.value);
    ui.updateSettings();
}
export function restoreOpeningOrderThreshold(){
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');
    const openingOrderThresholdState = localStorage.getItem('v4_opening-order-threshold');
    if (openingOrderThresholdState !== null) {
        openingOrderThresholdInput.value = openingOrderThresholdState;
    }
}

/*paused charts timeout*/
export function savePausedChartsTimeout() {
    const pausedChartsTimeoutInput = document.getElementById('paused-charts-timeout');
    localStorage.setItem('v4_paused-charts-timeout', pausedChartsTimeoutInput.value);
    ui.updateSettings();
}
export function restorePausedChartsTimeout(){
    const pausedChartsTimeoutInput = document.getElementById('paused-charts-timeout');
    const pausedChartsTimeoutState = localStorage.getItem('v4_paused-charts-timeout');
    if (pausedChartsTimeoutState !== null) {
        pausedChartsTimeoutInput.value = pausedChartsTimeoutState;
    }
}

/*stuck-timeout-mult */
export function saveStuckTimeoutMult() {
    const stuckTimeoutMultInput = document.getElementById('stuck-timeout-mult');
    localStorage.setItem('v4_stuck-timeout-mult', stuckTimeoutMultInput.value);
    ui.updateSettings();
}
export function restoreStuckTimeoutMult(){
    const stuckTimeoutMultInput = document.getElementById('stuck-timeout-mult');
    const stuckTimeoutMultState = localStorage.getItem('v4_stuck-timeout-mult');
    if (stuckTimeoutMultState !== null) {
        stuckTimeoutMultInput.value = stuckTimeoutMultState;
    }
}

/*Group order bultiplier*/
export function saveGroupOrderMultiplier() {
    const groupOrderMultiplierInput = document.getElementById('group-order-multiplier');
    localStorage.setItem('v4_group-order-multiplier', groupOrderMultiplierInput.value);
    ui.updateSettings();
}
export function restoreGroupOrderMultiplier(){
    const groupOrderMultiplierInput = document.getElementById('group-order-multiplier');
    const groupOrderMultiplierState = localStorage.getItem('v4_group-order-multiplier');
    if (groupOrderMultiplierState !== null) {
        groupOrderMultiplierInput.value = groupOrderMultiplierState;
    }
}

/*Closing Order Multiplier*/
export function saveClosingOrderMultiplier() {
    const closingOrderMultiplierInput = document.getElementById('closing-order-multiplier');
    localStorage.setItem('v4_closing-order-multiplier', closingOrderMultiplierInput.value);
    ui.updateSettings();
}
export function restoreClosingOrderMultiplier(){
    const closingOrderMultiplierInput = document.getElementById('closing-order-multiplier');
    const closingOrderMultiplierState = localStorage.getItem('v4_closing-order-multiplier');
    if (closingOrderMultiplierState !== null) {
        closingOrderMultiplierInput.value = closingOrderMultiplierState;
    }
}

/*closing timeout*/
export function saveClosingTimeout() {
    const closingTimeoutInput = document.getElementById('closing-timeout');
    localStorage.setItem('v4_closing-timeout', closingTimeoutInput.value);
    ui.updateSettings();
}
export function restoreClosingTimeout(){
    const closingTimeoutInput = document.getElementById('closing-timeout');
    const closingTimeoutState = localStorage.getItem('v4_closing-timeout');
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
    window.toggleAlgoVwap = toggleAlgoVwap;
    window.toggleAlgoFlat = toggleAlgoFlat;
    window.toggleAlgoScalp = toggleAlgoScalp;
    window.saveClosingTimeout = saveClosingTimeout;
}
exportToWindow();