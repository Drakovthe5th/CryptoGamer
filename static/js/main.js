// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;

// Load user balance
async function loadBalance() {
    const response = await fetch('/miniapp/balance', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-User': tg.initDataUnsafe.user.id,
            'X-Telegram-Hash': tg.initData
        }
    });
    
    const data = await response.json();
    if (data.success) {
        document.getElementById('balance').textContent = `Balance: ${data.balance} XNO`;
    }
}

// Play game
function playGame(gameType) {
    // Send request to play game
}

// Initialize
tg.ready();
tg.expand();
loadBalance();
