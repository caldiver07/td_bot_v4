let tickIntervalId = null;

function stopTicking() {
    if (tickIntervalId !== null) {
        clearInterval(tickIntervalId);
        tickIntervalId = null;
    }
}

self.addEventListener('message', (event) => {
    const data = event.data || {};

    if (data.command === 'start') {
        const interval = Number(data.interval) || 1000;

        stopTicking();
        self.postMessage({ type: 'tick' });
        tickIntervalId = self.setInterval(() => {
            self.postMessage({ type: 'tick' });
        }, interval);
        self.postMessage({ type: 'status', message: `started:${interval}` });
        return;
    }

    if (data.command === 'stop') {
        stopTicking();
        self.postMessage({ type: 'status', message: 'stopped' });
    }
});