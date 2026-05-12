
// import * as global from './global.js';
// import * as intf from './interface.js';

import * as utils from './utils.js';
import * as ui from './ui.js';

// Account INFO.....
document.getElementById('get-account-info').addEventListener('click', fetchAccountInfo);

export function fetchAccountInfo() {

    const url = `/account-info/`;

    fetch(url)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch account info');
            }
            return response.json();
        })
        .then((data) => {
            updateAccountInfo(data);
        })
        .catch((error) => {
            console.error('Error fetching account info:', error);
        });
}

export function updateAccountInfo(data) {
    if (data && Array.isArray(data)) {
        const accountSelect = document.getElementById('account-select');
        
        // Clear existing options except the placeholder
        accountSelect.innerHTML = '<option value="">-- Select Account --</option>';
        
        // Populate dropdown with accounts
        data.forEach(account => {
            const option = document.createElement('option');
            option.value = account.account_id;
            option.textContent = account.account_id;
            accountSelect.appendChild(option);
        });
        
        // Get saved account from localStorage or use first account
        let selectedAccountId = localStorage.getItem('v4_selectedAccount');
        if (!selectedAccountId && data.length > 0) {
            selectedAccountId = data[0].account_id;
            localStorage.setItem('v4_selectedAccount', selectedAccountId);
        }
        
        // Set the selected account in dropdown
        accountSelect.value = selectedAccountId;
        
        // Find and display the selected account's data
        const selectedAccount = data.find(acc => acc.account_id === selectedAccountId);
        if (selectedAccount) {
            displayAccountData(selectedAccount);
        }
        
        // Add event listener for account selection changes
        accountSelect.addEventListener('change', (e) => {
            const newAccountId = e.target.value;
            if (newAccountId) {
                localStorage.setItem('v4_selectedAccount', newAccountId);
                const account = data.find(acc => acc.account_id === newAccountId);
                if (account) {
                    displayAccountData(account);
                    ui.updateSettings();
                }
            }
        });
    }
}

function displayAccountData(account) {
    const balance = utils.formatAsCurrency(account.balance);
    const buying_power = utils.formatAsCurrency(account.buying_power);
    const day_change = utils.formatAsCurrency(account.day_change);
    const timestamp = utils.getTimestamp();

    const accountValue = document.getElementById('account-value');
    accountValue.textContent = balance;
    const buyingPower = document.getElementById('buying-power');
    buyingPower.textContent = buying_power;
    const dayChange = document.getElementById('day-change');
    dayChange.textContent = day_change;
    const accountTimestamp = document.getElementById('account-timestamp');
    accountTimestamp.textContent = `Updated: ${timestamp}`;
}