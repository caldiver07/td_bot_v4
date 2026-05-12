import * as main from './main.js';
import * as chart from './charts.js';
import * as status from './status.js';

export function updateSettings() {
    const autoTradingCheckbox = document.getElementById('auto-trading');

    const orderTimeoutInput = document.getElementById('order-timeout');
    
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');

    const closingOrderMultiplierInput = document.getElementById('closing-order-multiplier');
    const closingTimeoutInput = document.getElementById('closing-timeout');
    const groupOrderMultiplierInput = document.getElementById('group-order-multiplier');

    const pausedChartsTimeoutInput = document.getElementById('paused-charts-timeout');

    const settings = {
        auto_trading: autoTradingCheckbox.checked,
        order_timeout: parseInt(orderTimeoutInput.value, 10),
        
        opening_fill_threshold: parseInt(openingFillThresholdInput.value, 10),
        closing_fill_threshold: parseInt(closingFillThresholdInput.value, 10),
        opening_order_threshold: parseInt(openingOrderThresholdInput.value, 10),

        paused_charts_timeout: parseInt(pausedChartsTimeoutInput.value, 10),

        closing_order_multiplier: parseFloat(closingOrderMultiplierInput.value),
        closing_timeout: parseInt(closingTimeoutInput.value, 10),
        group_order_multiplier: parseFloat(groupOrderMultiplierInput.value),
        account_number: localStorage.getItem('selectedAccount')
    };

    fetch('/update-settings/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Settings updated:', data);
    })
    .catch((error) => {
        console.error('Error updating settings:', error);
    });
}

export function generatePayload(symbol) {
    //loop and create payload
    const payload = {
        'symbol': symbol,
        'trade': typeof status !== 'undefined' && status.getTradeSetting ? status.getTradeSetting(symbol) : false,
    };
    return payload;
}
export function loadChartSettings(){

    const payload = {};

    fetch('/load-chart-settings/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Settings loaded:', data);
    })
    .catch((error) => {
        console.error('Error loading settings:', error);
    });
}

export function updateChartSettings(symbol){

    const payload = generatePayload(symbol);

    fetch('/update-chart-settings/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Settings updated:', data);
    })
    .catch((error) => {
        console.error('Error updating settings:', error);
    });
}

export function updatePausedCharts(pausedCharts) {
    const pausedChartsInput = document.getElementById('paused-charts-count');
    const pausedChartsThresholdInput = document.getElementById('paused-charts-threshold');

    pausedChartsInput.textContent = JSON.stringify(pausedCharts);
    // Only check if threshold input exists
    if (pausedChartsThresholdInput) {
        if (pausedCharts >= parseInt(pausedChartsThresholdInput.value, 10)) {
            pausedChartsInput.classList.add('warning');
        } else {
            pausedChartsInput.classList.remove('warning');
        }
    }
}

export function updateOrderCount(count){
    const orderCountInput = document.getElementById('orders-count');
    orderCountInput.textContent = count;
}
