
import * as ui from './ui.js';
import * as utils from './utils.js';

export function generateStatusTable(data) {
    // Convert object of charts to array, filtering out non-chart entries
    const charts = Object.entries(data)
        .filter(([key]) => key.startsWith('chart_'))
        .map(([, chart]) => chart);
    
    if (!charts || charts.length === 0) {
        return generateEmptyStatusTable();
    }

    const tableRows = charts
        .map(chart => {
            const symbol = chart.symbol || '';
            const rank = chart.rank || '';
            const algoType = chart.algo_type || '';

            // Open and Cloase Counts....
            const closingOrderCount = chart.stats?.closing_order_count || 0;
            const closingOrderCountRolling = chart.stats?.closing_order_count_rolling || 0;
            const openingOrderCount = chart.stats?.opening_order_count || 0;
            const openingOrderCountRolling = chart.stats?.opening_order_count_rolling || 0;
            const closingOrderFilled = chart.stats?.closing_order_filled || 0;
            const closingOrderFilledRolling = chart.stats?.closing_order_filled_rolling || 0;
            const openingOrderFilled = chart.stats?.opening_order_filled || 0;
            const openingOrderFilledRolling = chart.stats?.opening_order_filled_rolling || 0;
            const closingOrderCanceled = chart.stats?.closing_order_canceled || 0;
            const closingOrderCanceledRolling = chart.stats?.closing_order_canceled_rolling || 0;
            const openingOrderCanceled = chart.stats?.opening_order_canceled || 0;
            const openingOrderCanceledRolling = chart.stats?.opening_order_canceled_rolling || 0;


            const openStatus = chart.order_opening?.status || '';
            const closeStatus = chart.order_closing?.status || '';
            const position = chart.position?.side || '';
            const spoofingDetected = chart.spoofing_detected || '';
            const smartDirection = chart.smart_direction || '';
            const trend = chart.trend || '';
            const volume = chart.volume || '';
            const level2Volume = chart.level_2_volume || '';
            const timeToClear = chart.time_to_clear || '';
            const bid = chart.bid || '';
            const ask = chart.ask || '';
            
            const chartDelay = chart.chart_time_delay !== null && chart.chart_time_delay !== undefined ? chart.chart_time_delay.toFixed(1) : '-';
            const setDelay = chart.set_time_delay !== null && chart.set_time_delay !== undefined ? chart.set_time_delay.toFixed(1) : '-';
            const delays = `${chartDelay}:${setDelay}`;

            const hasHighDelay = (chart.chart_time_delay > 2) || (chart.set_time_delay > 2);
            const delayClass = hasHighDelay ? 'text-red' : '';
            
            let openBotStatus = chart.order_opening?.bot_status || '';
            let closeBotStatus = chart.order_closing?.bot_status || '';
            const pausedOrders = chart.pause_orders || false;
            const tradeOrder = chart.trade_order || false;
            const groupOrder = chart.group_order || false;
            let pausedReason = chart.paused_reason || "";
            
            let orderOpeningTimeout = chart.order_opening?.timeout_seconds || '';
            let orderClosingTimeout = chart.order_closing?.timeout_seconds || '';

            const openingOrderFilledPercentRolling = chart.stats?.opening_order_filled_percent_rolling || '0';
            const closingOrderFilledPercentRolling = chart.stats?.closing_order_filled_percent_rolling || '0';

            const openingOrderFilledPercent = chart.stats?.opening_order_filled_percent || '0';
            const closingOrderFilledPercent = chart.stats?.closing_order_filled_percent || '0';

            let paused = utils.formatToOneDecimals(chart.stats?.paused);
            
            let fillOpoenPercentClass = 'text-green';
            let fillClosePercentClass = 'text-green';


            if (tradeOrder == false) {
                openBotStatus = 'Off'
                closeBotStatus = 'Off'
                pausedReason = '';
            }

            if (pausedOrders && pausedReason === "opening") {
                fillOpoenPercentClass = 'text-red';
            }
            if (pausedOrders && pausedReason === "closing") {
                fillClosePercentClass = 'text-red';
            }

            if (openBotStatus == 'Countdown') {
                openBotStatus = 'CD';
            } else if (openBotStatus == 'Shift' || openBotStatus == 'Canceling' || openBotStatus == 'Timeout' || openBotStatus == 'Paused') {
                // Keep the timeout text visible
            } else {
                orderOpeningTimeout = '';
            }

            if (closeBotStatus == 'Countdown') {
                closeBotStatus = 'CD';
            } else if (closeBotStatus == 'Shift' || closeBotStatus == 'Canceling' || closeBotStatus == 'Timeout' || closeBotStatus == 'Paused') {
                // Keep the timeout text visible
            } else {
                orderClosingTimeout = '';
            }
            // if (pausedOrders) {
            //     openBotStatus = 'Paused'
            // }

            const openNotReady = openStatus == 'WORKING' ;
            const closeNotReady = closeStatus == 'WORKING' ;
            const highlightClass = (openNotReady || closeNotReady) ? 'status-row-highlight' : '';

            return `
                <tr class="${highlightClass}">
                    <td class="status-symbol ${tradeOrder ? 'trade-active' : ''}" id="status-symbol-${symbol}">
                        <div class="symbol-container">
                            <span class="symbol-name">${symbol}</span>
                            <button class="reset-stats-btn" onclick="resetStats('${symbol}')" title="Reset Stats">RST</button>
                        </div>
                    </td>
                    <td class="rank" >${rank}</td>
                    <td class="algo" >${algoType}</td>
                    <td class="paused" data-status="${pausedOrders ? 'Paused' : 'Active'}">${pausedOrders ? 'Paused' : 'Active'}</td>
                    <td class="time" >${paused}</td>
                    <td class="open-bot" data-status="${openBotStatus}">${openBotStatus} ${orderOpeningTimeout}</td>
                    <td class="reason" data-status="${pausedReason}">${pausedReason}</td>
                    <td class="open-fill">${openingOrderCountRolling}/${openingOrderFilledRolling}/${openingOrderCanceledRolling} : ${openingOrderCount}/${openingOrderFilled}/${openingOrderCanceled}</td>
                    <td class="open-fill-pct ${fillOpoenPercentClass}">${openingOrderFilledPercentRolling} : ${openingOrderFilledPercent}</td>
                    <td class="open-status" data-status="${openStatus}">${openStatus}</td>
                    <td class="close-bot" data-status="${closeBotStatus}">${closeBotStatus} ${orderClosingTimeout}</td>
                    
                    <td class="close-fill">${closingOrderCountRolling}/${closingOrderFilledRolling}/${closingOrderCanceledRolling} : ${closingOrderCount}/${closingOrderFilled}/${closingOrderCanceled}</td>
                    <td class="close-fill-pct ${fillClosePercentClass}">${closingOrderFilledPercentRolling} : ${closingOrderFilledPercent}</td>


                    <td class="close-status" data-status="${closeStatus}">${closeStatus}</td>
                    <td class="position" >${position}</td>
                    <td class="spoofing" data-status="${spoofingDetected}">${spoofingDetected}</td>
                    <td class="smart-dir" data-status="${smartDirection}">${smartDirection}</td>
                    <td class="trend" data-status="${trend}">${trend}</td>
                    <td class="volume">${volume}</td>
                    <td class="l2-volume">${level2Volume}</td>
                    <td class="ttc" data-status="${timeToClear > 100 ? 'high' : ''}">${timeToClear}</td>
                    <td class="bid">${bid}</td>
                    <td class="ask" >${ask}</td>
                    <td class="delays ${delayClass}" >${delays}</td>
                    <td class="trade" ><input type="checkbox" id="trade-order-${symbol}" onchange="toggleTradeOrder('${symbol}')" ${tradeOrder ? 'checked' : ''}></td>
                </tr>
            `;
        })
        .join('');

    return `
        <table class="status-table">
            <thead>
                <tr>
                    <th class="status-symbol">Symbol</th>
                    <th class="rank">Rank</th>
                    <th class="algo">Algo</th>
                    <th class="paused">Paused</th>
                    <th class="time">Time</th>
                    <th class="open-bot">Open Bot</th>
                    <th class="reason">Reason</th>
                    <th class="open-fill">Open Fill</th>
                    <th class="open-fill-pct">Open Fill %</th>
                    <th class="open-status">Open Status</th>
                    <th class="close-bot">Close Bot</th>
                    <th class="close-fill">Close Fill</th>
                    <th class="close-fill-pct">Close Fill %</th>
                    <th class="close-status">Close Status</th>
                    <th class="position">Position</th>
                    <th class="spoofing">Spoofing</th>
                    <th class="smart-dir">Smart Dir</th>
                    <th class="trend">Trend</th>
                    <th class="volume">Vol</th>                    
                    <th class="l2-volume">L2 Vol</th>                    
                    <th class="ttc">TTC</th>                    
                    <th class="bid">Bid</th>
                    <th class="ask">Ask</th>
                    <th class="delays">Delays</th>
                    <th class="trade">Trade</th>
                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
    `;
}
function generateEmptyStatusTable() {
    return `
        <table class="status-table">
            <thead>
                <tr>
                    <th class="status-symbol">Symbol</th>
                    <th class="rank">Rank</th>
                    <th class="algo">Algo</th>
                    <th class="paused">Paused</th>
                    <th class="time">Time</th>
                    <th class="open-bot">Open Bot</th>
                    <th class="reason">Reason</th>
                    <th class="open-fill">Open Fill</th>
                    <th class="open-fill-pct">Open Fill %</th>
                    <th class="open-status">Open Status</th>
                    <th class="close-bot">Close Bot</th>
                    <th class="close-fill">Close Fill</th>
                    <th class="close-fill-pct">Close Fill %</th>
                    <th class="close-status">Close Status</th>
                    <th class="position">Position</th>
                    <th class="spoofing">Spoofing</th>
                    <th class="smart-dir">Smart Dir</th>
                    <th class="trend">Trend</th>
                    <th class="volume">Vol</th>                    
                    <th class="l2-volume">L2 Vol</th>                    
                    <th class="ttc">TTC</th>                    
                    <th class="bid">Bid</th>
                    <th class="ask">Ask</th>
                    <th class="delays">Delays</th>
                    <th class="trade">Trade</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="24" class="table-empty-message">No status information found</td>
                </tr>
            </tbody>
        </table>
    `;
}

export function getSelectedSymbolFromStatus(symbol) {
    const statusSymbol = document.getElementById(`status-symbol-${symbol}`);
    const localStoreageStatusSymbole = localStorage.getItem(`v4_chart_symbol_${symbol}`);
    if (localStoreageStatusSymbole) {
        return localStoreageStatusSymbole;
    }
    if (statusSymbol) {
        return symbol;
    }
    return null;
}

///// Manage Trade settings.....
export function restoreTradeOrderState() {
    const payloads = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('v4_tradeOrder_')) {
            const symbol = key.replace('v4_tradeOrder_', '');
            const isTrade = localStorage.getItem(key) === 'true';
            payloads.push({
                'symbol': symbol,
                'trade': isTrade
            });
        }
    }
    
    if (payloads.length > 0) {
        fetch('/update-chart-settings/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payloads),
        })
        .then(response => response.json())
        .then(data => console.log('All Chart settings restored:', data))
        .catch(error => console.error('Error restoring chart settings:', error));
    }
}
export function toggleTradeOrder(symbol) {
    const localStorageKey = `v4_tradeOrder_${symbol}`;
    const tradeOrderCheckbox = document.getElementById(`trade-order-${symbol}`);
    const chartSymbol = document.getElementById(`chart-symbol-${symbol}`);
    const statusSymbol = document.getElementById(`status-symbol-${symbol}`);

    if (tradeOrderCheckbox) {
        const isChecked = tradeOrderCheckbox.checked;
        localStorage.setItem(localStorageKey, isChecked.toString());
        
        if (isChecked) {
            if (chartSymbol) chartSymbol.classList.add('trade-active');
            if (statusSymbol) statusSymbol.classList.add('trade-active');
        } else {
            if (chartSymbol) chartSymbol.classList.remove('trade-active');
            if (statusSymbol) statusSymbol.classList.remove('trade-active');
        }
    }
    // update backend with new settings....
    ui.updateChartSettings(symbol);
}
export function getTradeSetting(symbol) {
    const localStorageKey = `v4_tradeOrder_${symbol}`;
    return localStorage.getItem(localStorageKey) === 'true';
}

export function exportToWindow() {
    window.restoreTradeOrderState = restoreTradeOrderState;
    window.toggleTradeOrder = toggleTradeOrder;
}
exportToWindow();

export function resetStats(symbol) {
    if (confirm(`Are you sure you want to reset stats for ` + symbol + `?`)) {
        fetch(`/reset-stats/` + symbol, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(response => response.json())
        .then(data => console.log('Stats reset:', data))
        .catch(error => console.error('Error resetting stats:', error));
    }
}
window.resetStats = resetStats;






