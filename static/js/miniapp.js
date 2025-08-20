// Initialize Telegram WebApp
document.addEventListener('DOMContentLoaded', function() {
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();

      // Get user data or create new user
    const initData = Telegram.WebApp.initDataUnsafe;
    const user_id = initData.user?.id;
    const username = initData.user?.username;

    if (user_id) {
      fetch('/api/user/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ user_id, username })
      })
      .then(response => response.json())
      .then(data => {
        if (data.is_new_user) {
          // Show welcome message
          Telegram.WebApp.showPopup({
            title: 'Welcome to CryptoGamer!',
            message: 'You received 2000 GC as a welcome bonus!',
            buttons: [{type: 'ok'}]
          });
        }});
  } else {
    document.body.innerHTML = `
      <div style="text-align:center;padding:50px 20px;">
        <h1>Please open in Telegram</h1>
        <p>This application must be opened within the Telegram messenger</p>
        <button style="margin-top:20px;padding:10px 20px;background:#0088cc;color:white;border:none;border-radius:8px;"
                onclick="window.location.href='https://t.me/Got3dBot'">
          Open in Telegram
        </button>
      </div>
    `;
  }
  initUserData(data);
  checkWalletConnection();
  loadGames();
}});

// DOM elements
const profileToggle = document.getElementById('profile-toggle');
const profileMenu = document.getElementById('profile-menu');
const closeMenu = document.getElementById('close-menu');
const username = document.getElementById('username');
const menuUsername = document.getElementById('menu-username');
const gcBalance = document.getElementById('gc-balance');
const menuBalance = document.getElementById('menu-balance');
const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');
const shopIcon = document.getElementById('shop-icon');
const shopModal = document.getElementById('shop-modal');
const closeShop = document.getElementById('close-shop');
const connectWalletBtn = document.getElementById('connect-wallet');
const disconnectWalletBtn = document.getElementById('disconnect-wallet');
const walletConnected = document.getElementById('wallet-connected');
const walletDisconnected = document.getElementById('wallet-disconnected');
const walletAddress = document.getElementById('wallet-address');
const claimBonus = document.getElementById('claim-bonus');
const dailyBonusPopup = document.getElementById('daily-bonus-popup');
const clickButton = document.getElementById('click-button');
const clickCount = document.getElementById('click-count');
const gamesContainer = document.getElementById('games-container');
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
const requestWithdrawal = document.getElementById('request-withdrawal');
const withdrawalProgress = document.getElementById('withdrawal-progress');
const progressText = document.getElementById('progress-text');
const copyLinkBtn = document.getElementById('copy-link');
const referralLink = document.getElementById('referral-link');

// Initialize user data
function initUserData() {
  username.textContent = window.userData.username;
  menuUsername.textContent = window.userData.username;
  gcBalance.textContent = `${window.userData.gameCoins.toLocaleString()} GC`;
  menuBalance.textContent = `${window.userData.gameCoins.toLocaleString()} GC`;
  
  // Update withdrawal progress
  const progressPercent = (window.userData.gameCoins / 200000) * 100;
  withdrawalProgress.style.width = `${progressPercent}%`;
  progressText.textContent = `${window.userData.gameCoins.toLocaleString()} / 200,000 GC`;
  
  // Enable withdrawal button if threshold reached
  if (window.userData.gameCoins >= 200000) {
    requestWithdrawal.disabled = false;
    requestWithdrawal.textContent = "Request Withdrawal (100 TON)";
  }
}

// Check if wallet is already connected
function checkWalletConnection() {
  const savedAddress = localStorage.getItem('ton_wallet_address');
  if (savedAddress) {
    walletAddress.textContent = `${savedAddress.substring(0, 6)}...${savedAddress.substring(savedAddress.length - 4)}`;
    walletConnected.classList.remove('hidden');
    walletDisconnected.classList.add('hidden');
  }
}

// Connect TON Wallet
function connectTONWallet() {
    if (window.Telegram && Telegram.WebApp) {
        // Use the correct Telegram method to connect wallet
        Telegram.WebApp.sendData(JSON.stringify({
            type: 'connect_wallet',
            timestamp: Date.now()
        }));
        
        // Listen for wallet connection response from Telegram
        Telegram.WebApp.onEvent('walletDataReceived', (data) => {
            try {
                const walletData = JSON.parse(data);
                if (walletData && walletData.address) {
                    localStorage.setItem('ton_wallet_address', walletData.address);
                    updateWalletDisplay(walletData.address);
                    Telegram.WebApp.showAlert(`Wallet connected: ${walletData.address}`);
                    
                    // Send wallet address to server
                    fetch('/api/wallet/connect', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Telegram-Hash': window.Telegram.WebApp.initData
                        },
                        body: JSON.stringify({ address: walletData.address })
                    }).catch(err => console.error('Error saving wallet:', err));
                }
            } catch (e) {
                console.error('Error parsing wallet data:', e);
            }
        });
    }
}

// Handle Telegram wallet connection response
function handleWalletConnection(data) {
    try {
        const walletData = JSON.parse(data);
        if (walletData && walletData.address) {
            localStorage.setItem('ton_wallet_address', walletData.address);
            updateWalletDisplay(walletData.address);
            
            // Send wallet address to server
            fetch('/api/wallet/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Hash': window.Telegram.WebApp.initData
                },
                body: JSON.stringify({ address: walletData.address })
            }).catch(err => console.error('Error saving wallet:', err));
        }
    } catch (e) {
        console.error('Error parsing wallet data:', e);
    }
}

function updateWalletDisplay(address) {
    const shortAddress = `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
    document.getElementById('wallet-address').textContent = shortAddress;
    document.getElementById('wallet-connected').classList.remove('hidden');
    document.getElementById('wallet-disconnected').classList.add('hidden');
}

// Disconnect wallet
function disconnectWallet() {
  localStorage.removeItem('ton_wallet_address');
  walletConnected.classList.add('hidden');
  walletDisconnected.classList.remove('hidden');
  Telegram.WebApp.showAlert('Wallet disconnected successfully');
}

// Switch pages
function switchPage(pageId) {
  // Hide all pages
  pages.forEach(page => {
    page.classList.remove('active');
  });
  
  // Show selected page
  document.getElementById(`${pageId}-page`).classList.add('active');
  
  // Update active nav item
  navItems.forEach(item => {
    item.classList.remove('active');
    if (item.getAttribute('data-page') === pageId) {
      item.classList.add('active');
    }
  });
}


// Update loadUserData to show GC
function loadUserData() {
    fetch('/api/user/data', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.game_coins !== undefined) {
            document.getElementById('gc-balance').textContent = data.game_coins;
            document.getElementById('ton-equivalent').textContent = (data.game_coins / 2000).toFixed(6);
        }
    });
}

// Load games with authentication
async function loadGames() {
  try {
    const response = await fetch('/api/games/list', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Security-Token': window.securityToken,
        'X-User-ID': window.userId
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const games = await response.json();
    renderGames(games);
    
  } catch (error) {
    console.error('Failed to load games:', error);
    Telegram.WebApp.showAlert('Failed to load games. Please try again later.');
  }
}

// Add OTC payment handling
function handleOTCSwap() {
    const amount = document.getElementById('otc-amount').value;
    const currency = document.querySelector('.currency-option.active').dataset.currency;
    
    let paymentPrompt = '';
    if (currency === 'KES') {
        paymentPrompt = 'Enter your phone number:';
    } else if (currency === 'USD' || currency === 'EUR') {
        paymentPrompt = 'Enter your PayPal email:';
    } else if (currency === 'USDT') {
        paymentPrompt = 'Enter your USDT wallet address:';
    }
    
    Telegram.WebApp.showPopup({
        title: `Confirm ${currency} Exchange`,
        message: paymentPrompt,
        buttons: [
            {type: 'cancel', text: 'Cancel'},
            {type: 'default', text: 'Confirm'}
        ]
    }, (btnId) => {
        if (btnId === 'confirm') {
            const paymentDetails = prompt(paymentPrompt);
            if (paymentDetails) {
                processExchange(amount, currency, paymentDetails);
            }
        }
    });
}

// Render games in grid
function renderGames(games) {
  gamesContainer.innerHTML = '';
  
  games.forEach(game => {
    const gameCard = document.createElement('div');
    gameCard.className = 'game-card';
    
    gameCard.innerHTML = `
      <div class="game-icon">${game.icon || '🎮'}</div>
      <div class="game-info">
        <h3>${game.name}</h3>
        <div class="game-reward">Earn up to ${game.reward || 5} $TON/hr</div>
      </div>
    `;

    gameCard.addEventListener('click', () => {
      Telegram.WebApp.showPopup({
        title: `Play ${game.name}`,
        message: `Start playing to earn ${game.reward || 5} TON coins per hour!`,
        buttons: [
          {id: 'cancel', type: 'cancel', text: 'Later'},
          {id: 'play', type: 'default', text: 'Play Now'}
        ]
      }, (btnId) => {
        if (btnId === 'play') {
          // Track game start event
          fetch('/api/game/start', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Security-Token': window.securityToken,
              'X-User-ID': window.userId
            },
            body: JSON.stringify({ game_id: game.id })
          });
          
          window.location.href = `/games/${game.id}`;
        }
      });
    });
    
    gamesContainer.appendChild(gameCard);
  });
}

// Claim daily bonus
function claimDailyBonus() {
  Telegram.WebApp.showPopup({
    title: "Bonus Claimed!",
    message: "You received 100 GC daily bonus",
    buttons: [{ type: "default", text: "OK" }]
  });
  
  // Update balance
  window.userData.gameCoins += 100;
  initUserData();
  
  // Hide bonus popup for today
  dailyBonusPopup.style.display = 'none';
  localStorage.setItem('lastBonusClaim', new Date().toDateString());
}

// Handle click game
let clickCountValue = 0;
function handleClick() {
  clickCountValue++;
  clickCount.textContent = clickCountValue;
  
  // Award GC every 10 clicks
  if (clickCountValue % 10 === 0) {
    window.userData.gameCoins += 1;
    initUserData();
    
    // Show floating +1 GC animation
    const plusOne = document.createElement('div');
    plusOne.textContent = '+1 GC';
    plusOne.style.position = 'absolute';
    plusOne.style.color = '#ffcc00';
    plusOne.style.fontWeight = 'bold';
    plusOne.style.animation = 'floatUp 1s forwards';
    clickButton.parentNode.appendChild(plusOne);
    
    setTimeout(() => {
      plusOne.remove();
    }, 1000);
  }
}

// Switch tabs
function switchTab(tabId) {
  tabPanes.forEach(pane => {
    pane.classList.remove('active');
  });
  
  tabBtns.forEach(btn => {
    btn.classList.remove('active');
  });
  
  document.getElementById(`${tabId}-tab`).classList.add('active');
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
}

// Request withdrawal
function requestWithdrawalFunc() {
  Telegram.WebApp.showPopup({
    title: "Withdrawal Request",
    message: "Your request to withdraw 100 TON has been submitted. It will be processed within 24 hours.",
    buttons: [{ type: "default", text: "OK" }]
  });
}

// Copy referral link
function copyReferralLink() {
  referralLink.select();
  document.execCommand('copy');
  
  Telegram.WebApp.showPopup({
    title: "Copied!",
    message: "Referral link copied to clipboard",
    buttons: [{ type: "default", text: "OK" }]
  });
}

// Event listeners
profileToggle.addEventListener('click', () => {
  profileMenu.classList.add('active');
});

closeMenu.addEventListener('click', () => {
  profileMenu.classList.remove('active');
});

navItems.forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const pageId = item.getAttribute('data-page');
    switchPage(pageId);
  });
});

shopIcon.addEventListener('click', () => {
  shopModal.classList.add('active');
});

closeShop.addEventListener('click', () => {
  shopModal.classList.remove('active');
});

connectWalletBtn.addEventListener('click', connectTONWallet);
disconnectWalletBtn.addEventListener('click', disconnectWallet);
claimBonus.addEventListener('click', claimDailyBonus);
clickButton.addEventListener('click', handleClick);
requestWithdrawal.addEventListener('click', requestWithdrawalFunc);
copyLinkBtn.addEventListener('click', copyReferralLink);

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const tabId = btn.getAttribute('data-tab');
    switchTab(tabId);
  });
});

// Check if daily bonus was already claimed today
const lastClaim = localStorage.getItem('lastBonusClaim');
if (lastClaim === new Date().toDateString()) {
  dailyBonusPopup.style.display = 'none';
}

// Add CSS for floating animation
const style = document.createElement('style');
style.textContent = `
  @keyframes floatUp {
    0% { 
      transform: translateY(0);
      opacity: 1;
    }
    100% { 
      transform: translateY(-30px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
  if (window.Telegram && Telegram.WebApp) {
    initUserData();
    checkWalletConnection();
    loadGames();
  }
});

// Simulate wallet connection event for demonstration
setTimeout(() => {
  window.postMessage({ 
    type: 'wallet_connected', 
    address: 'EQDrjaMAd1uyVtVb1hECV3a6F5Kc_ZLrjV7lLp7DZqNJiA1D' 
  }, '*');
}, 2000);