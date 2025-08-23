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

// main.js - Enhanced with Attachment Menu and Pagination support
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
  
  // Check for attachment menu deep links
  checkAttachmentMenuDeepLink();
});

// ==================== ATTACHMENT MENU FUNCTIONS ====================

/**
 * Check if the app was launched from an attachment menu deep link
 */
function checkAttachmentMenuDeepLink() {
  const urlParams = new URLSearchParams(window.location.search);
  const attachMenuLink = urlParams.get('attach_menu');
  
  if (attachMenuLink) {
    // Parse deep link data
    const deepLinkData = parseAttachMenuDeepLink(attachMenuLink);
    
    if (deepLinkData) {
      // Show attachment menu installation dialog
      showAttachMenuInstallDialog(deepLinkData.botId, deepLinkData.startParam);
    }
  }
}

/**
 * Parse attachment menu deep link
 */
function parseAttachMenuDeepLink(link) {
  try {
    // Example: https://t.me/your_bot/attach?bot_id=12345&start_param=ref123
    const url = new URL(link);
    const botId = url.searchParams.get('bot_id');
    const startParam = url.searchParams.get('start_param');
    
    return { botId, startParam };
  } catch (error) {
    console.error('Error parsing attachment menu deep link:', error);
    return null;
  }
}

/**
 * Show attachment menu installation dialog
 */
async function showAttachMenuInstallDialog(botId, startParam) {
  try {
    // Get bot info
    const botInfo = await API.call(`/api/attach-menu/bot/${botId}`);
    
    if (botInfo.success) {
      const botData = botInfo.bot;
      
      // Check if already installed
      if (!botData.inactive) {
        // Already installed, just open the mini app
        openMiniApp(botId, startParam);
        return;
      }
      
      // Show installation dialog
      const dialogHtml = `
        <div class="attach-menu-dialog">
          <h3>Install ${botData.short_name}</h3>
          <p>Add this mini app to your Telegram attachment menu for quick access?</p>
          
          ${botData.side_menu_disclaimer_needed ? `
            <div class="tos-checkbox">
              <input type="checkbox" id="accept-tos">
              <label for="accept-tos">
                I accept the <a href="https://telegram.org/tos/mini-apps" target="_blank">Mini Apps TOS</a>
                and understand this app is not affiliated with Telegram
              </label>
            </div>
          ` : ''}
          
          <div class="dialog-buttons">
            <button class="btn btn-secondary" onclick="closeAttachMenuDialog()">Cancel</button>
            <button class="btn btn-primary" id="install-btn" 
                    ${botData.side_menu_disclaimer_needed ? 'disabled' : ''}
                    onclick="installAttachMenuBot('${botId}', '${startParam}')">
              Install
            </button>
          </div>
        </div>
      `;
      
      // Show dialog
      showModal('attach-menu-dialog', dialogHtml);
      
      // Enable install button when TOS is accepted
      if (botData.side_menu_disclaimer_needed) {
        document.getElementById('accept-tos').addEventListener('change', function() {
          document.getElementById('install-btn').disabled = !this.checked;
        });
      }
    }
  } catch (error) {
    console.error('Error showing attach menu dialog:', error);
    showToast('Failed to load bot information', 'error');
  }
}

/**
 * Install attachment menu bot
 */
async function installAttachMenuBot(botId, startParam) {
  try {
    showSpinner();
    
    const result = await API.call('/api/attach-menu/install', {
      method: 'POST',
      body: JSON.stringify({ 
        bot_id: botId,
        write_allowed: true // Request write access if needed
      })
    });
    
    if (result.success) {
      showToast('Mini app installed successfully!');
      closeAttachMenuDialog();
      
      // Open the mini app after installation
      openMiniApp(botId, startParam);
    } else {
      showToast('Installation failed: ' + (result.error || 'Unknown error'), 'error');
    }
  } catch (error) {
    console.error('Error installing attach menu bot:', error);
    showToast('Installation failed', 'error');
  } finally {
    hideSpinner();
  }
}

/**
 * Open mini app from attachment menu
 */
function openMiniApp(botId, startParam) {
  // This would typically use Telegram.WebApp.openLink or similar
  // For now, we'll just show a success message
  showToast('Mini app opened successfully!');
  
  // You might navigate to a specific part of your app based on startParam
  if (startParam && startParam.startsWith('ref-')) {
    // Handle referral parameter
    const refCode = startParam.substring(4);
    handleReferral(refCode);
  }
}

/**
 * Close attachment menu dialog
 */
function closeAttachMenuDialog() {
  closeModal('attach-menu-dialog');
}

// ==================== PAGINATION FUNCTIONS ====================

/**
 * Generic paginated data loader
 */
async function loadPaginatedData(endpoint, containerId, itemRenderer, options = {}) {
  const {
    page = 1,
    limit = 10,
    hash = 0,
    append = false,
    loadingElement = null
  } = options;
  
  try {
    // Show loading state
    if (loadingElement) {
      loadingElement.style.display = 'block';
    }
    
    // Make API call with pagination parameters
    const response = await API.call(
      `${endpoint}?page=${page}&limit=${limit}&hash=${hash}`
    );
    
    if (response.not_modified) {
      // Data hasn't changed, use cached version
      return { not_modified: true };
    }
    
    if (response.success) {
      const container = document.getElementById(containerId);
      
      // Clear container if not appending
      if (!append) {
        container.innerHTML = '';
      }
      
      // Render items
      response.data.forEach(item => {
        const itemElement = itemRenderer(item);
        container.appendChild(itemElement);
      });
      
      // Create pagination controls if needed
      if (response.pagination && response.pagination.total_pages > 1) {
        createPaginationControls(
          containerId + '-pagination',
          response.pagination,
          (newPage) => {
            loadPaginatedData(
              endpoint, 
              containerId, 
              itemRenderer, 
              { ...options, page: newPage }
            );
          }
        );
      }
      
      return response;
    } else {
      showToast('Failed to load data', 'error');
      return null;
    }
  } catch (error) {
    console.error('Error loading paginated data:', error);
    showToast('Error loading data', 'error');
    return null;
  } finally {
    if (loadingElement) {
      loadingElement.style.display = 'none';
    }
  }
}

/**
 * Create pagination controls
 */
function createPaginationControls(containerId, pagination, onPageChange) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  const { current_page, total_pages, has_prev, has_next } = pagination;
  
  let controlsHtml = `
    <div class="pagination-controls">
      <button class="pagination-btn" ${!has_prev ? 'disabled' : ''} 
              onclick="onPageChange(${current_page - 1})">
        &laquo; Prev
      </button>
      
      <span class="pagination-info">
        Page ${current_page} of ${total_pages}
      </span>
      
      <button class="pagination-btn" ${!has_next ? 'disabled' : ''} 
              onclick="onPageChange(${current_page + 1})">
        Next &raquo;
      </button>
    </div>
  `;
  
  container.innerHTML = controlsHtml;
}

/**
 * Generate hash for pagination (based on Telegram's algorithm)
 */
function generatePaginationHash(ids) {
  let hash = 0;
  
  for (const id of ids) {
    hash = hash ^ (hash >>> 21);
    hash = hash ^ (hash << 35);
    hash = hash ^ (hash >>> 4);
    hash = hash + id;
  }
  
  return hash;
}

// ==================== ENHANCED LOAD FUNCTIONS ====================

/**
 * Enhanced user data loader with pagination support
 */
async function loadUserData() {
  try {
    const response = await API.call('/api/user/data', {
      headers: {
        'X-Telegram-Hash': window.Telegram.WebApp.initData
      }
    });
    
    if (response.balance !== undefined) {
      document.querySelectorAll('#balance').forEach(el => {
        el.textContent = `Balance: ${data.balance.toFixed(6)} TON`;
      });
    }
    
    if (response.staked) {
      document.querySelectorAll('#staked-amount').forEach(el => {
        el.textContent = data.staked.toFixed(6);
      });
    }
    
    if (response.rewards) {
      document.querySelectorAll('#staked-rewards').forEach(el => {
        el.textContent = data.rewards.toFixed(6);
      });
    }

    // Game coins display
    if (response.gameCoins) {
      document.querySelectorAll('#gc-balance').forEach(el => {
        el.textContent = `${response.gameCoins} GC`;
      });
    }
    
    // Load installed attachment menu bots
    if (response.attachMenuBots) {
      renderAttachMenuBots(response.attachMenuBots);
    }
  } catch (error) {
    console.error('Error loading user data:', error);
  }
}

/**
 * Render installed attachment menu bots
 */
function renderAttachMenuBots(bots) {
  const container = document.getElementById('installed-bots-container');
  if (!container || !bots || bots.length === 0) return;
  
  let html = '<h3>Your Mini Apps</h3><div class="bots-grid">';
  
  bots.forEach(bot => {
    html += `
      <div class="bot-item" data-bot-id="${bot.bot_id}">
        <img src="${bot.icon_url}" alt="${bot.short_name}" class="bot-icon">
        <div class="bot-name">${bot.short_name}</div>
        <button class="bot-action" onclick="openAttachMenuBot('${bot.bot_id}')">
          Open
        </button>
      </div>
    `;
  });
  
  html += '</div>';
  container.innerHTML = html;
}

/**
 * Open an installed attachment menu bot
 */
function openAttachMenuBot(botId) {
  // This would use Telegram's API to open the mini app
  // For now, we'll show a notification
  showToast('Opening mini app...');
  
  // In a real implementation, you might use:
  // Telegram.WebApp.openLink(`https://t.me/your_bot/attach?bot_id=${botId}`);
}

/**
 * Enhanced leaderboard loader with pagination
 */
async function loadLeaderboard(page = 1) {
  const loadingElement = document.getElementById('leaderboard-loading');
  const containerId = 'leaderboard-list';
  
  await loadPaginatedData(
    '/api/leaderboard',
    containerId,
    (user) => {
      const element = document.createElement('div');
      element.className = 'leaderboard-item';
      element.innerHTML = `
        <span class="rank">#${user.rank}</span>
        <span class="username">${user.username}</span>
        <span class="score">${user.score}</span>
      `;
      return element;
    },
    {
      page,
      limit: 20,
      loadingElement
    }
  );
}

// ==================== ENHANCED UI COMPONENTS ====================

/**
 * Show a modal with specific content
 */
function showModal(id, content) {
  let modal = document.getElementById(id);
  
  if (!modal) {
    // Create modal if it doesn't exist
    modal = document.createElement('div');
    modal.id = id;
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-content">
        <span class="close-modal" onclick="closeModal('${id}')">&times;</span>
        <div class="modal-body">${content}</div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  
  modal.style.display = 'block';
}

/**
 * Close a modal
 */
function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.style.display = 'none';
  }
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'info') {
  // Remove existing toasts
  const existingToasts = document.querySelectorAll('.toast');
  existingToasts.forEach(toast => toast.remove());
  
  // Create new toast
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  // Animate in
  setTimeout(() => {
    toast.classList.add('show');
  }, 10);
  
  // Remove after delay
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, 3000);
}

// ==================== INITIALIZATION ====================

// Initialize pagination for various sections
document.addEventListener('DOMContentLoaded', function() {
  // Load leaderboard with pagination
  loadLeaderboard();
  
  // Load transaction history with pagination
  loadTransactionHistory();
  
  // Load other paginated data as needed
});

/**
 * Load transaction history with pagination
 */
async function loadTransactionHistory(page = 1) {
  const loadingElement = document.getElementById('transactions-loading');
  const containerId = 'transactions-list';
  
  await loadPaginatedData(
    '/api/transactions',
    containerId,
    (transaction) => {
      const element = document.createElement('div');
      element.className = 'transaction-item';
      element.innerHTML = `
        <span class="transaction-date">${new Date(transaction.date).toLocaleDateString()}</span>
        <span class="transaction-type">${transaction.type}</span>
        <span class="transaction-amount ${transaction.amount >= 0 ? 'positive' : 'negative'}">
          ${transaction.amount >= 0 ? '+' : ''}${transaction.amount}
        </span>
      `;
      return element;
    },
    {
      page,
      limit: 15,
      loadingElement
    }
  );
}
