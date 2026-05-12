import * as utils from './utils.js';
import * as status from './status.js';

document.getElementById('get-positions').addEventListener('click', fetchPositions);

export function fetchPositions() {

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

    const positionsUrl = `/account-positions`;
    fetch(positionsUrl)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch account positions');
            }
            return response.json();
        })
        .then((data) => {
            const positionsInfoDiv = document.getElementById('positions-info');
            const statusInfoDiv = document.getElementById('status-info');
            const statusTimestampDiv = document.getElementById('status-timestamp');
            statusTimestampDiv.textContent = `Updated: ${timestamp}`;
            const positionsTimestampDiv = document.getElementById('positions-timestamp');
            positionsTimestampDiv.textContent = `Updated: ${timestamp}`;

            if (data) {
                const position_data = data.positions;
                const stream_data = data.stream;

                positionsInfoDiv.innerHTML = `
                    ${generatePositionsTable(position_data)}
                `;
                
                const statusHTML = status.generateStatusTable(data.stream);
                statusInfoDiv.innerHTML = statusHTML;

            } else {
                // Generate empty table when no positions
                positionsInfoDiv.innerHTML = `
                    ${generateEmptyPositionsTable()}
                `;
            }
        })
        .catch((error) => {
            console.error('Failed to fetch account positions. Please try again.' + error.message);
        });
}
export function generatePositionsTable(positions) {
    const tableRows = positions
        .map(
            (position) => `
            <tr>
                <td class="positions-symbol">${position.symbol}</td>
                <td>${position.quantity}</td>
                <td>${position.market_value}</td>
                <td class="positions-side">${position.side}</td>
            </tr>
        `
        )
        .join('');

    return `
        <table class="positions-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Market Value</th>
                    <th>Side</th>
                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
    `;
}
export function generateEmptyPositionsTable() {
    return `
        <table class="positions-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Market Value</th>
                    <th>Side</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="4" class="table-empty-message">No open positions found</td>
                </tr>
            </tbody>
        </table>
    `;
}
