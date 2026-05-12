import * as utils from './utils.js';
import * as status from './status.js';

/// Orders INFO.....
document.getElementById('get-orders').addEventListener('click', fetchOrders);


export function fetchOrders() {
    // Update timestamp immediately when button is clicked
    const now = new Date();
    const timestamp = now.toLocaleString('en-US', {
        month: '2-digit',
        day: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });

    const ordersUrl = `/account-orders`;
    fetch(ordersUrl)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch account orders a');
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
                    ${generateOrdersTable(order_data, true)}
                `;

                const statusHTML = status.generateStatusTable(data.stream);
                statusInfoDiv.innerHTML = statusHTML;

            } else {
                ordersInfoDiv.innerHTML = `
                    ${generateEmptyOrdersTable()}
                `;
                const statusHTML = status.generateStatusTable([]);
                statusInfoDiv.innerHTML = statusHTML;
            }
        })
        .catch((error) => {
            console.error('Error fetching account orders:', error);
        });
}
export function generateOrdersTable(orders, isWorkingOrders = false) {
    if (!orders || orders.length === 0) {
        return generateEmptyOrdersTable();
    }

    const tableRows = orders
        .map(
            (order) => {
                const status = order.status || 'N/A';
                const instruction = order.instruction || order.side || 'N/A';
                const price = order.price ? '$' + parseFloat(order.price).toFixed(2) : 'Market';
                const orderId = order.order_id || order.id || 'N/A';

                // Add cancel button only for working orders
                const cancelButton = isWorkingOrders ?
                    `<button class="cancel-btn" onclick="cancelOrder('${orderId}', '${order.symbol}')">Cancel</button>` :
                    '';

                return `
                <tr data-status="${status}" data-order-id="${orderId}">
                    <td>${order.symbol || 'N/A'}</td>
                    <td>${order.entered_time || ''}</td>
                    <td>${order.position_effect || ''}</td>
                    <td>${order.fill_time_seconds || ''}</td>
                    <td>${order.order_id || 'N/A'}</td>
                    <td>${order.parent_order_id || ''}</td>
                    <td>${order.strategy_type || 'N/A'}</td>
                    <td class="${instruction.toLowerCase()}">${instruction}</td>
                    <td>${order.orderType || order.type || 'N/A'}</td>
                    <td>${status}</td>
                </tr>
            `;
            }
        )
        .join('');

    const headers = `
        <th>Symbol</th>
        <th>Time</th>
        <th>Effect</th>
        <th>Time</th>
        <th>Order ID</th>
        <th>Parent Order</th>
        <th>Strategy</th>
        <th>Side</th>
        <th>Type</th>
        <th>Status</th>`;

    return `
        <table class="orders-table">
            <thead>
                <tr>
                    ${headers}
                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
    `;
}
export function generateEmptyOrdersTable() {
    return `
        <table class="orders-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Side</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="8" class="table-empty-message">No working orders found</td>
                </tr>
            </tbody>
        </table>
    `;
}

