import * as utils from './utils.js';
import * as ui from './ui.js'
import * as main from './main.js';

const chartInstances = new Map(); // Store chart instances

const chartConfig = {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            {
                label: 'Bid',
                data: [],
                borderColor: 'rgba(74, 133, 63, 1)', // Blue color for bid
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                pointRadius: 0,
            },
            {
                label: 'Ask',
                data: [],
                borderColor: 'rgba(136, 79, 66, 1)', // Orange color for ask
                backgroundColor: 'rgba(255, 159, 64, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                pointRadius: 0,
            },
            {
                label: 'Last',
                data: [],
                borderColor: 'rgba(180, 192, 75, 1)', // Green color for last
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                pointRadius: 0,
            },
            {
                label: 'Volume',
                data: [],
                backgroundColor: 'rgba(128, 128, 128, 0.5)',
                borderColor: 'rgba(128, 128, 128, 0.8)',
                type: 'bar',
                yAxisID: 'y2'
            }
        ]
    },
    options: {
        animation: {
            duration: 0
        },
        responsive: true,
        plugins: {
            title: {
                display: true,
                text: 'Real-Time Market Data', // This will be updated dynamically
                font: {
                    size: 14,
                    weight: 'bold'
                },
                color: '#ffffff',
                align: 'start'
            },
            legend: {
                position: 'right', // Move legend to the right
                align: 'start',   // Align legend items to start (top)
                labels: {
                    color: '#a2a1a1ff',    // White text for dark theme
                    font: {
                        size: 12
                    },
                    padding: 15,         // Add padding between legend items
                    usePointStyle: true  // Use point style instead of rectangles
                }
            }
        },
        scales: {
            x: {
                title: {
                    display: false,
                    text: 'Time',
                },
                type: 'category', // Use category scale
                ticks: {
                    maxTicksLimit: false, // Remove tick limit to show all labels
                    maxRotation: 45,      // Rotate labels for better readability
                    minRotation: 0,
                    autoSkip: false,      // Don't skip any labels
                    callback: function(value, index, values) {
                        // Return all labels without filtering
                        return this.getLabelForValue(value);
                    }
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Price',
                },
            },
            y2: {
                type: 'linear',
                display: true,
                position: 'right',
                title: {
                    display: true,
                    text: 'Volume'
                },
                grid: {
                    drawOnChartArea: false
                }

            }
        }

    }
};

export function loadCharts() {
    for (let i = 1; i <= main.numberOfCharts; i++) {
        const canvasId = `bid-ask-chart-${i}`;
        createChart(canvasId);
    }
}

export function createChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');
    
    // Create a deep copy of chartConfig for each chart instance
    const configCopy = JSON.parse(JSON.stringify(chartConfig));
    
    const chart = new Chart(ctx, configCopy);
    
    // Store the chart instance
    chartInstances.set(canvasId, chart);
    
    return chart;
}

export function updateChartTitle(chartId, title) {
    // Get the chart instance, not the canvas
    const chart = chartInstances.get(chartId);
    console.log(`Updated title for ${chartId} to "${title}"`);
    if (chart) {
        chart.options.plugins.title.text = title;
        chart.update();
    } else {
        console.error(`Chart instance not found for ID: ${chartId}`);
    }
}

export function updateChartData(chartId, timestamp_list, bids_list, asks_list, last_list, volume_list) {
    const chart = chartInstances.get(chartId);
    //console.log(`Updating data for ${chartId}` +
    //    ` Timestamps: ${timestamp_list.length}, Bids: ${bids_list.length}, Asks: ${asks_list.length}, Last: ${last_list.length}, Volume: ${volume_list.length}`);
    if (chart) {
        chart.data.labels = timestamp_list;
        chart.data.datasets[0].data = bids_list; 
        chart.data.datasets[1].data = asks_list;
        chart.data.datasets[2].data = last_list;
        chart.data.datasets[3].data = volume_list; 
        chart.update('none'); // 'none' to disable animation for real-time updates
    }
}

export function getChartInstance(chartId) {
    return chartInstances.get(chartId);
}

export function updateChartPauseStatus(chartNumber, isPaused) {
    const symbolElement = document.getElementById(`chart-symbol-${chartNumber}`);
    if (symbolElement) {
        if (isPaused) {
            symbolElement.classList.add('group-paused');
        } else {
            symbolElement.classList.remove('group-paused');
        }
    }
}

export function setSymbolAndFilledPercent(chart_number, symbol, stats) {
    const element = document.getElementById(`chart-symbol-${chart_number}`);
    element.style.display = 'flex';
    element.style.justifyContent = 'space-between';
    let age = utils.formatToOneDecimals(stats.age);
    let duration = utils.formatToOneDecimals(stats.duration);
    let paused = utils.formatToOneDecimals(stats.paused);
    element.innerHTML = `
        <span id="symbol-${chart_number}-value">${symbol}</span>
        <span>A/D/P: ${age}/${duration}/${paused}</span>
    `;
}

export function setBidAskInfo(chart_number, data) {
    const pauseThresholdInput = document.getElementById('pause-threshold');
    const pauseThreshold2Input = document.getElementById('pause-threshold-2');
    const currentChangeThresholdInput = document.getElementById('current-change-threshold');
    const openingFillThresholdInput = document.getElementById('opening-fill-threshold');
    const closingFillThresholdInput = document.getElementById('closing-fill-threshold');
    const openingOrderThresholdInput = document.getElementById('opening-order-threshold');

    const element = document.getElementById(`bidask-info-${chart_number}`);
    const pauseClass = data.pause_orders === true ? 'negative' : 'positive';
    let fillPercentClass = 'text-green';
    if (data.stats.filled_buy_percent < parseInt(openingFillThresholdInput.value, 10) && data.stats.adj_buy_count >= 10) {
        fillPercentClass = 'text-red';
    } else if (data.stats.filled_buy_percent < (parseInt(openingFillThresholdInput.value, 10)+10) && data.stats.adj_buy_count >= 10) {
        fillPercentClass = 'text-yellow';
    }
    let chartChangeClass = 'text-green';
    if (data.stats.chart_change > parseInt(pauseThresholdInput.value, 10) ) {
        chartChangeClass = 'text-red';
    } else if (data.stats.chart_change > (parseInt(pauseThresholdInput.value, 10)-2)) {
        chartChangeClass = 'text-yellow';
    }

    let currentChangeClass = 'text-green';
    if (data.stats.current_change > parseInt(currentChangeThresholdInput.value, 10) || data.stats.chart_change > parseInt(pauseThreshold2Input.value, 10)) {
        currentChangeClass = 'text-red';
    }
    element.innerHTML = `
        <div style="display: flex; justify-content: space-between; gap: 5px; white-space: nowrap;">
            <div style="flex: 1;">
                <span class="highlight-name">Timestamp:</span><span class="highlight-value">${data.tmstamp}</span>
                <span class="highlight-name">Bid:</span><span class="highlight-value">${data.bid}</span>
                <span class="highlight-name">Ask:</span><span class="highlight-value">${data.ask}</span>
                <span class="highlight-name">Gap:</span><span class="highlight-value">${data.ba_gap}</span>
            </div>
            <div style="flex: 1;">
                <span class="highlight-name">Chart Status:</span><span class="highlight-value status-${data.stats.chart_status.toLowerCase().replace(' ', '-')}">${data.stats.chart_status}</span>
                <span class="highlight-name">Current Status:</span><span class="highlight-value status-${data.stats.current_status.toLowerCase().replace(' ', '-')}">${data.stats.current_status}</span>
                <span class="highlight-name">Chart Change:</span><span class="highlight-value ${chartChangeClass}">${data.stats.chart_change}</span>
                <span class="highlight-name">Current Change:</span><span class="highlight-value ${currentChangeClass}">${data.stats.current_change}</span>
                <span class="highlight-name">Buy:</span><span class="highlight-value">${data.stats.opening_order_count}/${data.stats.opening_order_filled}/${data.stats.opening_order_canceled}</span>
                <span class="highlight-name"></span><span class="highlight-value ${fillPercentClass}">${data.stats.opening_order_filled_percent}%</span>
                <span class="highlight-name">Pause Orders:</span><span class="highlight-value ${pauseClass}">${data.pause_orders}</span>
            </div>
        </div>
    `;
}



///// Manage Trigger settings.....
export function restoreTriggerOrderState() {
    for (let i = 1; i <= main.numberOfCharts; i++) {
        const localStorageKey = `triggerOrder_${i}`;
        const triggerOrderState = localStorage.getItem(localStorageKey)  === 'true';
        const triggerOrderCheckbox = document.getElementById(`trigger-order-${i}`);
        const chartSymbol = document.getElementById(`chart-symbol-${i}`);
        if (triggerOrderCheckbox) {
            triggerOrderCheckbox.checked = triggerOrderState;
        }
        if (triggerOrderState) {
            chartSymbol.classList.add('trigger-active');
        } else {
            chartSymbol.classList.remove('trigger-active');
        }
    }
}
export function toggleTriggerOrder(symbol) {
    const localStorageKey = `triggerOrder_${symbol}`;
    const triggerOrderCheckbox = document.getElementById(`trigger-order-${symbol}`);
    const chartSymbol = document.getElementById(`status-symbol-${symbol}`);
    if (triggerOrderCheckbox) {
        const isChecked = triggerOrderCheckbox.checked;
        localStorage.setItem(localStorageKey, isChecked.toString());
        if (isChecked) {
            chartSymbol.classList.add('trigger-active');
        } else {
            chartSymbol.classList.remove('trigger-active');
        }
    }
    // update backend with new settings....
    ui.updateChartSettings();
}
export function getTriggerSetting(symbol) {
    const localStorageKey = `triggerOrder_${symbol}`;
    return localStorage.getItem(localStorageKey) === 'true';
}

/// Manage Group settings.....
export function toggleGroupOrder(chartIndex) {
    const localStorageKey = `groupOrder_${chartIndex}`;
    const groupOrderCheckbox = document.getElementById(`group-order-${chartIndex}`);
    const chartSymbol = document.getElementById(`chart-symbol-${chartIndex}`);
    const statusSymbol = document.getElementById(`status-symbol-${chartIndex}`);
    if (groupOrderCheckbox) {
        const isChecked = groupOrderCheckbox.checked;
        localStorage.setItem(localStorageKey, isChecked.toString());

        if (isChecked) {
            if (chartSymbol) chartSymbol.classList.add('group-active');
            if (statusSymbol) statusSymbol.classList.add('group-active');
        } else {
            if (chartSymbol) chartSymbol.classList.remove('group-active');
            if (statusSymbol) statusSymbol.classList.remove('group-active');
        }
    }
    // update backend with new settings....
    ui.updateChartSettings();
}
export function restoreGroupOrderState() {
    for (let i = 1; i <= main.numberOfCharts; i++) {
        const localStorageKey = `groupOrder_${i}`;
        const groupOrderState = localStorage.getItem(localStorageKey)  === 'true';
        const groupOrderCheckbox = document.getElementById(`group-order-${i}`);
        const chartSymbol = document.getElementById(`chart-symbol-${i}`);
        const statusSymbol = document.getElementById(`status-symbol-${i}`);
        if (groupOrderCheckbox) {
            groupOrderCheckbox.checked = groupOrderState;
        }
        if (groupOrderState) {
            if (chartSymbol) chartSymbol.classList.add('group-active');
            if (statusSymbol) statusSymbol.classList.add('group-active');
        } else {
            if (chartSymbol) chartSymbol.classList.remove('group-active');
            if (statusSymbol) statusSymbol.classList.remove('group-active');
        }
    }
}
export function getGroupSetting(chartIndex) {
    const localStorageKey = `groupOrder_${chartIndex}`;
    return localStorage.getItem(localStorageKey) === 'true';
}


export function exportToWindow() {
    window.getChartInstance = getChartInstance;
    window.updateChartTitle = updateChartTitle;
    window.loadCharts = loadCharts;
    window.restoreTriggerOrderState = restoreTriggerOrderState;
    window.toggleTriggerOrder = toggleTriggerOrder;
    window.toggleGroupOrder = toggleGroupOrder;
    window.restoreGroupOrderState = restoreGroupOrderState;
}
exportToWindow();
