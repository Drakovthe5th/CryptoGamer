document.addEventListener('DOMContentLoaded', function() {
    // Initialize Telegram Web App
    const webApp = window.Telegram.WebApp;
    webApp.expand();
    webApp.enableClosingConfirmation();
    
    // Load user data
    loadUserData();
    
    // Set up event listeners
    document.querySelectorAll('button').forEach(button => {
        button.addEventListener('click', handleButtonClick);
    });
});

function loadUserData() {
    fetch('/api/user/data', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.balance !== undefined) {
            document.getElementById('balance').textContent = 
                `Balance: ${data.balance.toFixed(6)} TON`;
        }
        
        // Load additional data based on page
        if (document.getElementById('daily-quests')) {
            loadQuests();
        }
        
        if (document.getElementById('ton-withdrawal-form')) {
            setupWithdrawalForms();
        }
    })
    .catch(error => {
        console.error('Error loading user data:', error);
    });
}

function handleButtonClick(event) {
    const button = event.target;
    const action = button.dataset.action;
    
    if (action) {
        switch(action) {
            case 'start-game':
                startGame(button.dataset.game);
                break;
            case 'claim-reward':
                claimReward(button.dataset.rewardId);
                break;
            case 'initiate-withdrawal':
                initiateWithdrawal();
                break;
        }
    }
}

function startGame(gameType) {
    fetch(`/api/games/start?game=${gameType}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Launch game interface based on gameType
            launchGameInterface(gameType);
        } else {
            alert('Failed to start game: ' + data.error);
        }
    });
}

function setupWithdrawalForms() {
    document.getElementById('ton-withdrawal-form').addEventListener('submit', function(e) {
        e.preventDefault();
        submitTonWithdrawal();
    });
    
    document.getElementById('otc-withdrawal-form').addEventListener('submit', function(e) {
        e.preventDefault();
        submitOtcWithdrawal();
    });
}

function submitTonWithdrawal() {
    const address = document.getElementById('ton-address').value;
    const amount = parseFloat(document.getElementById('ton-amount').value);
    
    fetch('/api/withdraw', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({
            method: 'ton',
            amount: amount,
            address: address
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Withdrawal successful! TX: ${data.tx_hash}`);
            loadUserData(); // Refresh balance
        } else {
            alert('Withdrawal failed: ' + data.error);
        }
    });
}

function submitOtcWithdrawal() {
    const amount = parseFloat(document.getElementById('otc-amount').value);
    const currency = document.getElementById('otc-currency').value;
    const method = document.getElementById('payment-method').value;
    
    // Get payment details based on method
    let paymentDetails = {};
    if (method === 'M-Pesa') {
        paymentDetails = { phone: document.getElementById('mpesa-phone').value };
    } else if (method === 'PayPal') {
        paymentDetails = { email: document.getElementById('paypal-email').value };
    } else if (method === 'Bank Transfer') {
        paymentDetails = {
            bankName: document.getElementById('bank-name').value,
            accountName: document.getElementById('account-name').value,
            accountNumber: document.getElementById('account-number').value,
            iban: document.getElementById('iban').value || ''
        };
    }
    
    fetch('/api/withdraw', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({
            method: 'otc',
            amount: amount,
            currency: currency,
            paymentMethod: method,
            details: paymentDetails
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Cash withdrawal processing! Deal ID: ${data.deal_id}`);
            loadUserData(); // Refresh balance
        } else {
            alert('Withdrawal failed: ' + data.error);
        }
    });
}