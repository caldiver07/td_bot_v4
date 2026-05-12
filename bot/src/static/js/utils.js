
// function to format numbers as currency
export function formatAsCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
    }).format(value);
}
export function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}
export function formatToTwoDecimals(value) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0.00';
    }
    return parseFloat(value).toFixed(2);
}
export function formatToOneDecimals(value) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0.00';
    }
    return parseFloat(value).toFixed(1);
}
export function getTimestamp() {
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
    return timestamp;
}