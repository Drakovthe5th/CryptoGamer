// WebSocket for real-time updates
function initWebSocket() {
    const socket = new WebSocket('wss://your-api-endpoint/ws');
    
    socket.onopen = function() {
        console.log('WebSocket connection established');
        const authData = {
            userId: Telegram.WebApp.initData.user?.id,
            hash: window.Telegram.WebApp.initData
        };
        socket.send(JSON.stringify(authData));
    };
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        switch(data.type) {
            case 'balance':
                document.getElementById('balance').textContent = 
                    `Balance: ${data.balance.toFixed(6)} TON`;
                break;
            case 'staking':
                document.getElementById('staked-amount').textContent = data.staked.toFixed(6);
                document.getElementById('staked-rewards').textContent = data.rewards.toFixed(6);
                break;
            case 'priceAlert':
                showPriceAlert(data);
                break;
            case 'event':
                showEventNotification(data);
                break;
        }
    };
    
    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
    
    socket.onclose = function() {
        console.log('WebSocket connection closed');
        setTimeout(initWebSocket, 5000); // Reconnect after 5 seconds
    };
}

function showPriceAlert(data) {
    const alertMsg = `TON price alert: $${data.price} reached!`;
    if (Notification.permission === 'granted') {
        new Notification('Price Alert', { body: alertMsg });
    } else {
        Telegram.WebApp.showAlert(alertMsg);
    }
}

function showEventNotification(data) {
    const notification = document.createElement('div');
    notification.className = 'event-notification';
    notification.innerHTML = `
        <h3>${data.title}</h3>
        <p>${data.message}</p>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}