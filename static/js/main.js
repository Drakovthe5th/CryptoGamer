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

// Show in-app interstitial ads
function initInterstitialAds() {
  show_9644715({
    type: 'inApp',
    inAppSettings: {
      frequency: 2,          // Show 2 ads
      capping: 0.1,          // Within 6 minutes
      interval: 30,          // 30-second interval between ads
      timeout: 5,            // 5-second delay before first ad
      everyPage: false       // Don't reset on page navigation
    }
  });
}

document.addEventListener('DOMContentLoaded', initInterstitialAds);

// Enhanced Security Features
function showAddAddressForm() {
    document.getElementById('address-modal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function saveAddress() {
    const address = document.getElementById('new-address').value;
    if (!address) return;
    
    // Save to backend
    fetch('/api/security/whitelist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ address })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Add to UI
            const li = document.createElement('li');
            li.textContent = address;
            document.getElementById('whitelist-addresses').appendChild(li);
            closeModal('address-modal');
        }
    });
}

// 2FA Toggle
document.getElementById('2fa-toggle').addEventListener('change', function() {
    if (this.checked) {
        // Enable 2FA
        fetch('/api/security/enable-2fa', {
            method: 'POST',
            headers: {
                'X-Telegram-Hash': window.Telegram.WebApp.initData
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('2fa-modal').style.display = 'block';
            }
        });
    } else {
        // Disable 2FA
        fetch('/api/security/disable-2fa', {
            method: 'POST',
            headers: {
                'X-Telegram-Hash': window.Telegram.WebApp.initData
            }
        });
    }
});

function verify2FA() {
    const code = document.getElementById('2fa-code').value;
    fetch('/api/security/verify-2fa', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ code })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            closeModal('2fa-modal');
        } else {
            alert('Invalid code');
        }
    });
}

// Premium Subscription
function subscribePremium() {
    fetch('/api/user/subscribe', {
        method: 'POST',
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Premium subscription activated!');
            loadUserData();
        } else {
            alert('Failed: ' + data.error);
        }
    });
}

// Referral Program
function copyRefLink() {
    const refInput = document.getElementById('ref-link');
    refInput.select();
    document.execCommand('copy');
    alert('Referral link copied!');
}

// Theme Toggle
document.getElementById('theme-toggle').addEventListener('click', function() {
    const isDark = document.body.classList.toggle('dark-theme');
    this.textContent = isDark ? '☀️' : '🌙';
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
});

// Language Selector
document.getElementById('lang').addEventListener('change', function() {
    const lang = this.value;
    localStorage.setItem('lang', lang);
    applyLanguage(lang);
});

function applyLanguage(lang) {
    // In a real app, this would load translation strings
    console.log('Language changed to', lang);
}

// Community Features
function openForum() {
    Telegram.WebApp.openLink('https://forum.cryptogameminer.com');
}

function openEvents() {
    // In a real app, this would show live events
    alert('Live events coming soon!');
}

function openFeedback() {
    Telegram.WebApp.showPopup({
        title: 'Feedback',
        message: 'Share your feedback with us',
        buttons: [
            { type: 'default', text: 'Submit', id: 'submit' }
        ]
    }, function(buttonId) {
        if (buttonId === 'submit') {
            const feedback = prompt('Enter your feedback:');
            if (feedback) {
                submitFeedback(feedback);
            }
        }
    });
}

function submitFeedback(feedback) {
    fetch('/api/feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ feedback })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Thank you for your feedback!');
        }
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // ... existing initialization ...
    
    // Load security data
    fetch('/api/security/data', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.whitelist) {
            data.whitelist.forEach(address => {
                const li = document.createElement('li');
                li.textContent = address;
                document.getElementById('whitelist-addresses').appendChild(li);
            });
        }
        
        if (data.is2FAEnabled) {
            document.getElementById('2fa-toggle').checked = true;
        }
    });
    
    // Load referral data
    fetch('/api/user/referrals', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.count) {
            document.getElementById('ref-count').textContent = data.count;
        }
        if (data.earnings) {
            document.getElementById('ref-earnings').textContent = data.earnings.toFixed(6);
        }
    });
});