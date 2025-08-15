// main.js - Core functionality shared across pages
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
    
    // Initialize theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.classList.toggle('light-theme', savedTheme === 'light');
    
    // Initialize language
    const savedLang = localStorage.getItem('lang') || 'en';
    document.getElementById('lang').value = savedLang;
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
            document.querySelectorAll('#balance').forEach(el => {
                el.textContent = `Balance: ${data.balance.toFixed(6)} TON`;
            });
        }
        
        if (data.staked) {
            document.querySelectorAll('#staked-amount').forEach(el => {
                el.textContent = data.staked.toFixed(6);
            });
        }
        
        if (data.rewards) {
            document.querySelectorAll('#staked-rewards').forEach(el => {
                el.textContent = data.rewards.toFixed(6);
            });
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
            case 'toggle-theme':
                toggleTheme();
                break;
        }
    }
}

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-theme');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
        themeBtn.textContent = isLight ? '🌙' : '☀️';
    }
}

function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show requested page
    document.getElementById(`${pageId}-page`).classList.add('active');
    
    // Update active nav button
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Set active nav button for main pages
    if (pageId !== 'profile') {
        const navBtns = document.querySelectorAll('.nav-btn');
        const pageIndex = ['home', 'watch', 'wallet', 'games', 'quests', 'otc', 'referrals'].indexOf(pageId);
        if (pageIndex !== -1) {
            navBtns[pageIndex].classList.add('active');
        }
    }
}

function showModal(modalId) {
    document.getElementById(modalId).style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Security functions
function showAddAddressForm() {
    showModal('address-modal');
}

function saveAddress() {
    const address = document.getElementById('new-address').value;
    if (!address) return;
    
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
            const li = document.createElement('li');
            li.textContent = address;
            document.getElementById('whitelist-addresses').appendChild(li);
            closeModal('address-modal');
        }
    });
}

// Initialize security features
document.addEventListener('DOMContentLoaded', function() {
    // Load security data
    fetch('/api/security/data', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.whitelist) {
            const list = document.getElementById('whitelist-addresses');
            if (list) {
                data.whitelist.forEach(address => {
                    const li = document.createElement('li');
                    li.textContent = address;
                    list.appendChild(li);
                });
            }
        }
        
        if (data.is2FAEnabled && document.getElementById('2fa-toggle')) {
            document.getElementById('2fa-toggle').checked = true;
        }
    });
});

// Global spinner control
function showSpinner() {
  document.getElementById('global-spinner').style.display = 'flex';
}

function hideSpinner() {
  document.getElementById('global-spinner').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    // Handle wallet actions
    document.querySelectorAll('.btn-action').forEach(button => {
        button.addEventListener('click', function() {
            const action = this.dataset.action;
            const amount = this.dataset.amount;
            
            fetch(`/api/blockchain/${action}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ amount })
            })
            .then(response => response.json())
            .then(data => {
                if(data.success) {
                    alert(`${action} successful!`);
                    updateBalanceDisplay();
                } else {
                    alert(`Error: ${data.error}`);
                }
            });
        });
    });
    
    // Update balance display
    function updateBalanceDisplay() {
        fetch('/api/user/balance')
            .then(response => response.json())
            .then(data => {
                document.getElementById('balance-display').textContent = data.balance;
            });
    }
    
    // Initialize balance display
    updateBalanceDisplay();
});

// Example usage in API calls
async function loadUserData() {
  showSpinner();
  try {
    // API call here
  } catch (error) {
    // Handle error
  } finally {
    hideSpinner();
  }
}