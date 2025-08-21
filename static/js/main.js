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

    // Game coins display
    if (data.gameCoins) {
      document.querySelectorAll('#gc-balance').forEach(el => {
        el.textContent = `${data.gameCoins} GC`;
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
      case 'purchase-item':
        purchaseItem(button.dataset.itemId);
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
    const pageIndex = ['home', 'shop', 'games', 'wallet', 'quests', 'otc', 'referrals'].indexOf(pageId);
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

// main.js - Update the loadGame function to use StaticPaths
// In main.js - Add enhanced error handling for Render
async function loadGame(gameType) {
    try {
        console.log(`🎮 Loading ${gameType} game...`);
        updateLoadingDetails(`Loading ${gameType} game...`);
        
        // Show loading state
        showGameLoading(gameType);
        
        // Haptic feedback
        hapticFeedback('selection');
        
        // Enable game-specific CSS and load JS using StaticPaths with retry
        try {
            if (window.StaticPaths && window.StaticPaths.loadGameAssets) {
                await window.StaticPaths.loadGameAssets(gameType, 3); // 3 retries
            } else {
                // Fallback to manual loading with retry
                await loadWithRetry(() => enableGameCSS(gameType), 3);
                await loadWithRetry(() => loadGameScript(gameType), 3);
            }
        } catch (error) {
            console.error(`Failed to load assets for ${gameType}:`, error);
            showToast(`Failed to load ${gameType} assets. Please try again.`, 'error');
            return;
        }
        
        // Load game HTML content with retry
        try {
            await loadWithRetry(() => loadGameHTML(gameType), 3);
        } catch (error) {
            console.error(`Failed to load HTML for ${gameType}:`, error);
            showToast(`Failed to load ${gameType}. Please try again.`, 'error');
            return;
        }
        
        // Initialize game
        try {
            await initializeGame(gameType);
        } catch (error) {
            console.error(`Failed to initialize ${gameType}:`, error);
            showToast(`Failed to initialize ${gameType}. Please try again.`, 'error');
            return;
        }
        
        // Update Telegram UI
        updateTelegramUI(gameType);
        
        console.log(`✅ ${gameType} game loaded successfully`);
        
    } catch (error) {
        console.error(`❌ Failed to load ${gameType} game:`, error);
        showToast(`Failed to load ${gameType} game. Please try again.`, 'error');
        hapticFeedback('notification', 'error');
    }
}

// Helper function for retry logic
async function loadWithRetry(operation, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await operation();
        } catch (error) {
            if (attempt === maxRetries) {
                throw error;
            }
            console.warn(`Attempt ${attempt} failed, retrying in ${attempt * 1000}ms...`);
            await new Promise(resolve => setTimeout(resolve, attempt * 1000));
        }
    }
}

// Update loading details for better user feedback
function updateLoadingDetails(message) {
    const detailsElement = document.getElementById('loading-details');
    if (detailsElement) {
        detailsElement.textContent = message;
    }
}

// Show retry button when loading fails
function showRetryButton() {
    const retryButton = document.getElementById('retry-button');
    if (retryButton) {
        retryButton.style.display = 'block';
    }
}

// Helper functions
function enableGameCSS(gameType) {
    // Disable all game CSS
    document.querySelectorAll('[id$="-css"]').forEach(css => {
        css.disabled = true;
    });
    
    // Enable specific game CSS
    const gameCSS = document.getElementById(`${gameType}-css`);
    if (gameCSS) {
        gameCSS.disabled = false;
    }
}

async function loadGameScript(gameType) {
    if (gameAssets.has(gameType)) {
        return; // Already loaded
    }
    
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        
        // Use StaticPaths if available, otherwise fallback
        if (window.StaticPaths && window.StaticPaths.games[gameType]) {
            script.src = window.StaticPaths.games[gameType].js;
        } else {
            script.src = `/game-assets/${gameType}/game.js`;
        }
        
        script.onload = () => {
            gameAssets.set(gameType, true);
            resolve();
        };
        script.onerror = () => reject(new Error(`Failed to load ${gameType} script`));
        document.head.appendChild(script);
    });
}

async function loadGameHTML(gameType) {
    try {
        // Use StaticPaths if available, otherwise fallback
        let gameHTMLUrl;
        if (window.StaticPaths && window.StaticPaths.games.html) {
            gameHTMLUrl = `${window.StaticPaths.games.html}${gameType}`;
        } else {
            gameHTMLUrl = `/games/${gameType}`;
        }
        
        const response = await fetch(gameHTMLUrl);
        if (!response.ok) {
            throw new Error(`Game ${gameType} not found`);
        }
        
        const gameHTML = await response.text();
        const gameContent = document.getElementById('game-content');
        gameContent.innerHTML = gameHTML;
        
        // Show game container
        document.getElementById('game-container').style.display = 'block';
        document.getElementById('app-container').style.display = 'none';
        
        // Update game title
        document.getElementById('current-game-title').textContent = 
            gameType.charAt(0).toUpperCase() + gameType.slice(1);
        
    } catch (error) {
        throw new Error(`Failed to load ${gameType} HTML: ${error.message}`);
    }
}

// Add basic API client functionality if api-client.js is missing
if (typeof window.API === 'undefined') {
    window.API = {
        call: async function(endpoint, options = {}) {
            try {
                const response = await fetch(endpoint, {
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-Hash': window.Telegram ? Telegram.WebApp.initData : ''
                    },
                    ...options
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                throw error;
            }
        }
    };
}

// Add basic state management if state-manager.js is missing
if (typeof window.StateManager === 'undefined') {
    window.StateManager = {
        state: {},
        listeners: [],
        
        setState: function(newState) {
            this.state = { ...this.state, ...newState };
            this.notifyListeners();
        },
        
        getState: function() {
            return this.state;
        },
        
        subscribe: function(listener) {
            this.listeners.push(listener);
            return () => {
                this.listeners = this.listeners.filter(l => l !== listener);
            };
        },
        
        notifyListeners: function() {
            this.listeners.forEach(listener => listener(this.state));
        }
    };
}

// Add basic component functionality if components.js is missing
if (typeof window.Components === 'undefined') {
    window.Components = {
        showToast: function(message, type = 'info') {
            if (window.Telegram && Telegram.WebApp) {
                Telegram.WebApp.showPopup({
                    title: type.charAt(0).toUpperCase() + type.slice(1),
                    message: message,
                    buttons: [{ type: 'ok' }]
                });
            } else {
                alert(message);
            }
        },
        
        showSpinner: function() {
            const spinner = document.getElementById('global-spinner');
            if (spinner) {
                spinner.style.display = 'flex';
            }
        },
        
        hideSpinner: function() {
            const spinner = document.getElementById('global-spinner');
            if (spinner) {
                spinner.style.display = 'none';
            }
        }
    };
}

// Rest of the main.js code remains the same
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

// Global spinner control
function showSpinner() {
  document.getElementById('global-spinner').style.display = 'flex';
}

function hideSpinner() {
  document.getElementById('global-spinner').style.display = 'none';
}

// Game launching function
function launchGame(gameId) {
  showSpinner();
  fetch(`/api/games/launch/${gameId}`, {
    headers: {
      'X-Telegram-Hash': window.Telegram.WebApp.initData
    }
  })
  .then(response => response.json())
  .then(data => {
    hideSpinner();
    if (data.url) {
      window.location.href = data.url;
    }
  })
  .catch(error => {
    hideSpinner();
    console.error('Error launching game:', error);
    Telegram.WebApp.showAlert('Failed to launch game. Please try again.');
  });
}

// Purchase function
function purchaseItem(itemId) {
  showSpinner();
  fetch(`/api/shop/purchase/${itemId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Hash': window.Telegram.WebApp.initData
    }
  })
  .then(response => response.json())
  .then(data => {
    hideSpinner();
    if (data.success) {
      Telegram.WebApp.showPopup({
        title: 'Purchase Complete!',
        message: `You bought ${data.itemName}`,
        buttons: [{type: 'ok'}]
      });
      // Update balance display
      loadUserData();
    } else {
      Telegram.WebApp.showAlert(`Purchase failed: ${data.error}`);
    }
  })
  .catch(error => {
    hideSpinner();
    console.error('Error purchasing item:', error);
    Telegram.WebApp.showAlert('Failed to purchase item. Please try again.');
  });
}