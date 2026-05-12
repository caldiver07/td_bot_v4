
import * as utils from './utils.js';
import * as orders from './orders.js';
import * as status from './status.js';
import * as ui from './ui.js';
import * as settings from './settings.js'
import * as account from './account.js'

let botCheckInterval = null;
let botWorker = null;
let botCheckStatus = false;
let accountInfoInterval = null;

export let numberOfCharts = 40;

export function disableTradeButton() {
    const goButton = document.getElementById('go-button');
    goButton.disabled = true;
    goButton.style.opacity = '0.5';
    goButton.style.cursor = 'not-allowed';
    goButton.style.pointerEvents = 'none';
}
export function enableTradeButton() {
    const goButton = document.getElementById('go-button');
    goButton.disabled = false;
    goButton.style.opacity = '1';
    goButton.style.cursor = 'pointer';
    goButton.style.pointerEvents = 'auto';
}

function updateGoButtonState(isRunning) {
    const goButton = document.getElementById('go-button');
    goButton.classList.toggle('active', isRunning);
    goButton.textContent = isRunning ? 'Stop' : 'Go';
}

function stopBotPolling() {
    if (botWorker !== null) {
        botWorker.postMessage({ command: 'stop' });
        botWorker.terminate();
        botWorker = null;
    }

    if (botCheckInterval !== null) {
        clearInterval(botCheckInterval);
        botCheckInterval = null;
    }

    updateGoButtonState(false);
    console.log('Bot check stopped');
}

function startBotPollingWithInterval() {
    checkBot();
    botCheckInterval = setInterval(checkBot, 1000);
    updateGoButtonState(true);
    console.log('Bot check started with window timer');
}

function startBotPollingWithWorker() {
    botWorker = new Worker(new URL('./botWorker.js', import.meta.url));

    botWorker.addEventListener('message', function(e) {
        if (e.data.type === 'tick') {
            checkBot();
        } else if (e.data.type === 'status') {
            console.log('Worker status:', e.data.message);
        }
    });

    botWorker.addEventListener('error', function(e) {
        console.error('Worker error:', e.message);
        stopBotPolling();
    });

    botWorker.postMessage({ command: 'start', interval: 1000 });

    updateGoButtonState(true);
    console.log('Bot check started with Web Worker');
}

document.getElementById('go-button').addEventListener('click', startBotCheck);
export function startBotCheck() {
    if (botWorker !== null || botCheckInterval !== null) {
        stopBotPolling();
        return;
    }

    if (typeof Worker !== 'function') {
        startBotPollingWithInterval();
        return;
    }

    try {
        startBotPollingWithWorker();
    } catch (error) {
        console.error('Unable to start Web Worker, falling back to window timer:', error);
        startBotPollingWithInterval();
    }
}

export function checkBot() {
    const timestamp = utils.getTimestamp();
    const botUrl = `/bot`;
    if (botCheckStatus) {
        console.error('Bot check already in progress');
        return;
    }
    botCheckStatus = true;
    fetch(botUrl)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch bot data');
            }
            return response.json();
        })
        .then((data) => {
            const ordersInfoDiv = document.getElementById('orders-info');
            const statusInfoDiv = document.getElementById('status-info');
            const statusTimestampDiv = document.getElementById('status-timestamp');
            statusTimestampDiv.textContent = `Updated: ${timestamp}`;
            const ordersTimestampDiv = document.getElementById('orders-timestamp');
            ordersTimestampDiv.textContent = `Updated: ${timestamp}`;

            if (data) {
                //console.log('Fetched account orders data:', data);
                const order_data = data.orders;
                const stream_data = data.stream;
                //console.log('Fetched account stream data:', stream_data);

                // Generate tables for working and filled orders
                ordersInfoDiv.innerHTML = `
                    ${orders.generateOrdersTable(order_data, true)}
                `;

                const statusHTML = status.generateStatusTable(data.stream);
                statusInfoDiv.innerHTML = statusHTML;

                updateStatusInfo(data);
                if (data.account && Array.isArray(data.account) && data.account.length > 0) {
                    account.updateAccountInfo(data.account);
                }

            } else {
                ordersInfoDiv.innerHTML = `
                    ${orders.generateEmptyOrdersTable()}
                `;
                const statusHTML = status.generateStatusTable([]);
                statusInfoDiv.innerHTML = statusHTML;
            }
            botCheckStatus = false;
        })
        .catch((error) => {
            console.error('Error fetching account orders:', error);
            botCheckStatus = false;
        });
}

export function updateStatusInfo(data){
    document.getElementById('phase-value').textContent = data.stats.phase;
    document.getElementById('status-value').textContent = data.stats.status;
    document.getElementById('sub-status-value').textContent = data.stats.sub_status;

    document.getElementById('message-value').textContent = data.stats.message;
    const messageElement = document.getElementById('message-value');
    const message = data.stats.message || '';
    messageElement.setAttribute('data-message', message);

    if (data.stream) {
        if (data.stream.order_count !== undefined) {
            ui.updateOrderCount(data.stream.order_count);
        }
        if (data.stream.paused_charts !== undefined) {
            ui.updatePausedCharts(data.stream.paused_charts);
        }
    }

    if (data.stats.status === 'Error') {
        startBotCheck();
        settings.setAutoTrading(false);
    }
}

window.addEventListener('load', () => {

    
    ui.loadChartSettings();
    account.fetchAccountInfo();

    /*update the setting from local store and then push to backend...*/
    settings.restoreOrderTimeout();
    
    settings.restoreOpeningFillThreshold();
    settings.restoreClosingFillThreshold();
    settings.restoreOpeningOrderThreshold();
    // settings.restoreStuckTimeoutMult();

    settings.restoreGroupOrderMultiplier();
    settings.restoreClosingOrderMultiplier();
    settings.restoreClosingTimeout();

    settings.restorePausedChartsTimeout();

    status.restoreTradeOrderState();

    ui.updateSettings();
});