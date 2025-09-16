const telegramWebEvents = new TelegramWebEvents();
let tonConnectUI = null;
let userData = null;
let clickCountValue = 0;

// Initialize Telegram WebApp
document.addEventListener('DOMContentLoaded', function() {
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
    Telegram.WebApp.setHeaderColor('#000000');
    Telegram.WebApp.setBackgroundColor('#000000');

    // Get user data or create new user
    const initData = Telegram.WebApp.initDataUnsafe;
    const user_id = initData.user?.id;
    const username = initData.user?.username;
    const is_premium = initData.user?.is_premium || false;

    // Initialize Web Events
    initTelegramWebEvents();
    
    // Initialize TON Connect
    initTONConnect();
    setupWalletMessageHandler();

    if (user_id) {
      fetch('/api/user/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ user_id, username, is_premium })
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
        }
        userData = data;
        initUserData(data);
        initAffiliateProgram();
        checkWalletOnLoad();
        
        // Check if daily bonus was already claimed today
        const lastClaim = localStorage.getItem('lastBonusClaim');
        const dailyBonusPopup = document.getElementById('daily-bonus-popup');
        if (dailyBonusPopup && lastClaim === new Date().toDateString()) {
          dailyBonusPopup.style.display = 'none';
        }
      })
      .catch(error => {
        console.error('Error initializing user:', error);
      });
    }
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
  
  // Set up event listeners after DOM is fully loaded
  setTimeout(setupEventListeners, 100);
  
  // Initialize navigation
  initNavigation();
});

function setupEventListeners() {
  // DOM elements
  const profileToggle = document.getElementById('profile-toggle');
  const profileMenu = document.getElementById('profile-menu');
  const closeMenu = document.getElementById('close-menu');
  const navItems = document.querySelectorAll('.nav-item');
  const shopIcon = document.getElementById('shop-icon');
  const shopModal = document.getElementById('shop-modal');
  const closeShop = document.getElementById('close-shop');
  const connectWalletBtn = document.getElementById('connect-wallet');
  const disconnectWalletBtn = document.getElementById('disconnect-wallet');
  const claimBonus = document.getElementById('claim-bonus');
  const clickButton = document.getElementById('click-button');
  const requestWithdrawal = document.getElementById('request-withdrawal');
  const copyLinkBtn = document.getElementById('copy-link');
  const tabBtns = document.querySelectorAll('.tab-btn');

  // Add event listeners if elements exist
  if (profileToggle) {
    profileToggle.addEventListener('click', () => {
      profileMenu.classList.add('active');
    });
  }

  if (closeMenu) {
    closeMenu.addEventListener('click', () => {
      profileMenu.classList.remove('active');
    });
  }

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const pageId = item.getAttribute('data-page');
      switchPage(pageId);
    });
  });

  if (shopIcon) {
    shopIcon.addEventListener('click', () => {
      shopModal.classList.add('active');
    });
  }

  if (closeShop) {
    closeShop.addEventListener('click', () => {
      shopModal.classList.remove('active');
    });
  }

  if (connectWalletBtn) {
    connectWalletBtn.addEventListener('click', connectTONWallet);
  }

  if (disconnectWalletBtn) {
    disconnectWalletBtn.addEventListener('click', disconnectWallet);
  }

  if (claimBonus) {
    claimBonus.addEventListener('click', claimDailyBonus);
  }

  if (clickButton) {
    clickButton.addEventListener('click', handleClick);
  }

  if (requestWithdrawal) {
    requestWithdrawal.addEventListener('click', requestWithdrawalFunc);
  }

  if (copyLinkBtn) {
    copyLinkBtn.addEventListener('click', copyReferralLink);
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // Add haptic feedback to interactive elements
  document.querySelectorAll('button, .game-card, .nav-item').forEach(element => {
    element.addEventListener('click', () => {
      triggerHapticFeedback('selection_change');
    });
  });
}

// Initialize Telegram Web Events
function initTelegramWebEvents() {
  // Setup main button
  telegramWebEvents.setupMainButton(true, true, 'Play Games', '#3390ec', '#ffffff', false, true);
  
  // Setup back button
  telegramWebEvents.setupBackButton(false);
  
  // Setup settings button
  telegramWebEvents.setupSettingsButton(true);
  
  // Listen for events from Telegram
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.onEvent('mainButtonClicked', () => {
      switchPage('games');
    });
    
    Telegram.WebApp.onEvent('backButtonClicked', () => {
      history.back();
    });
    
    Telegram.WebApp.onEvent('settingsButtonClicked', () => {
      const profileMenu = document.getElementById('profile-menu');
      if (profileMenu) profileMenu.classList.add('active');
    });
    
    Telegram.WebApp.onEvent('invoiceClosed', (eventData) => {
      handleInvoiceClosed(eventData);
    });
    
    Telegram.WebApp.onEvent('walletDataReceived', (data) => {
      handleWalletConnection(data);
    });
  }
}

// Handle invoice closed event
function handleInvoiceClosed(eventData) {
  const { slug, status } = eventData;
  
  if (status === 'paid') {
    // Process successful payment
    Telegram.WebApp.showPopup({
      title: 'Payment Successful',
      message: 'Your purchase has been completed!',
      buttons: [{ type: 'default', text: 'OK' }]
    });
    
    // Update user balance or unlock features
    loadUserData();
  } else if (status === 'failed' || status === 'cancelled') {
    Telegram.WebApp.showPopup({
      title: 'Payment Cancelled',
      message: 'Your payment was not completed.',
      buttons: [{ type: 'default', text: 'OK' }]
    });
  }
}

// Trigger haptic feedback
function triggerHapticFeedback(type, impactStyle, notificationType) {
  telegramWebEvents.triggerHapticFeedback(type, impactStyle, notificationType);
}

// Share score
function shareScore(score, game) {
  telegramWebEvents.shareScore(score, game);
}

// Share game
function shareGame(game) {
  telegramWebEvents.shareGame(game);
}

// Open Telegram invoice
function openTelegramInvoice(slug) {
  telegramWebEvents.openInvoice(slug);
}

// Initialize TON Connect
function initTONConnect() {
  try {
    const manifestUrl = window.location.origin + '/tonconnect-manifest.json';
    
    tonConnectUI = new TonConnectUI({
      manifestUrl: manifestUrl,
      buttonRootId: 'ton-connect-button',
      language: 'en',
      uiPreferences: {
        theme: Telegram.WebApp.colorScheme || 'dark'
      }
    });

    // Handle connection status changes
    tonConnectUI.onStatusChange(wallet => {
      if (wallet) {
        // Wallet connected
        const address = wallet.account.address;
        updateWalletDisplay(address);
        
        // Send wallet address to server
        fetch('/api/wallet/connect', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram ? Telegram.WebApp.initData : ''
          },
          body: JSON.stringify({ 
            address: address,
            provider: wallet.provider,
            device: wallet.device
          })
        }).then(response => response.json())
        .then(data => {
          if (data.success) {
            console.log('Wallet connection saved');
          }
        }).catch(err => console.error('Error saving wallet:', err));
      } else {
        // Wallet disconnected
        const walletConnected = document.getElementById('wallet-connected');
        const walletDisconnected = document.getElementById('wallet-disconnected');
        
        if (walletConnected && walletDisconnected) {
          walletConnected.classList.add('hidden');
          walletDisconnected.classList.remove('hidden');
        }
        
        // Clear local storage
        localStorage.removeItem('ton_wallet_address');
      }
    });

    // Check initial connection status
    if (tonConnectUI.wallet) {
      updateWalletDisplay(tonConnectUI.wallet.account.address);
    }
  } catch (error) {
    console.error('Error initializing TON Connect:', error);
    // Fallback to manual connection method
    initManualWalletConnection();
  }
}

// Manual wallet connection fallback
function initManualWalletConnection() {
  console.log('Using manual wallet connection fallback');
  
  // Check if wallet is already connected
  const savedAddress = localStorage.getItem('ton_wallet_address');
  if (savedAddress) {
    updateWalletDisplay(savedAddress);
  }
  
  // Override connect function
  window.connectTONWallet = function() {
    if (window.Telegram && Telegram.WebApp) {
      Telegram.WebApp.openLink('https://t.me/wallet?startattach=wallet_connect');
    } else {
      alert('Please open in Telegram to connect your wallet');
    }
  };
}

// Connect to TON wallet
async function connectTONWallet() {
  try {
    // Try TON Connect first
    if (tonConnectUI) {
      tonConnectUI.openModal();
      return;
    }
    
    // Fallback to Telegram native wallet
    if (window.Telegram && Telegram.WebApp) {
      const result = await Telegram.WebApp.sendData(JSON.stringify({
        type: 'connect_wallet'
      }));
      
      if (result && result.address) {
        handleWalletConnection(result);
      }
    }
  } catch (error) {
    console.error('Wallet connection failed:', error);
    Telegram.WebApp.showAlert('Failed to connect wallet. Please try again.');
  }
}

// Handle Telegram wallet connection response
function handleWalletConnection(data) {
  try {
    const walletData = typeof data === 'string' ? JSON.parse(data) : data;
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

// Update wallet display
function updateWalletDisplay(address) {
  if (!address) return;
  
  const walletAddress = document.getElementById('wallet-address');
  const walletConnected = document.getElementById('wallet-connected');
  const walletDisconnected = document.getElementById('wallet-disconnected');
  
  if (!walletAddress || !walletConnected || !walletDisconnected) return;
  
  const shortAddress = `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  walletAddress.textContent = shortAddress;
  walletConnected.classList.remove('hidden');
  walletDisconnected.classList.add('hidden');
  
  // Save to local storage for fallback
  localStorage.setItem('ton_wallet_address', address);
}

// Disconnect wallet
function disconnectWallet() {
  if (tonConnectUI) {
    tonConnectUI.disconnect();
  }
  localStorage.removeItem('ton_wallet_address');
  
  const walletConnected = document.getElementById('wallet-connected');
  const walletDisconnected = document.getElementById('wallet-disconnected');
  
  if (walletConnected && walletDisconnected) {
    walletConnected.classList.add('hidden');
    walletDisconnected.classList.remove('hidden');
  }
  
  Telegram.WebApp.showAlert('Wallet disconnected successfully');
}

// Check if wallet is already connected
function checkWalletOnLoad() {
  // Check TON Connect first
  if (tonConnectUI && tonConnectUI.wallet) {
    updateWalletUI(true, tonConnectUI.wallet.account.address);
    return;
  }
  
  // Check localStorage fallback
  const savedAddress = localStorage.getItem('ton_wallet_address');
  if (savedAddress) {
    updateWalletUI(true, savedAddress);
  }
}

// Update wallet UI
function updateWalletUI(isConnected, address = null) {
  const walletConnected = document.getElementById('wallet-connected');
  const walletDisconnected = document.getElementById('wallet-disconnected');
  const walletAddress = document.getElementById('wallet-address');
  
  if (!walletConnected || !walletDisconnected || !walletAddress) return;
  
  if (isConnected && address) {
    // Format address for display
    const shortAddress = `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
    walletAddress.textContent = shortAddress;
    walletConnected.classList.remove('hidden');
    walletDisconnected.classList.add('hidden');
    
    // Save to localStorage for persistence
    localStorage.setItem('ton_wallet_address', address);
  } else {
    walletConnected.classList.add('hidden');
    walletDisconnected.classList.remove('hidden');
    localStorage.removeItem('ton_wallet_address');
  }
}

// Add secure wallet message handling
function setupWalletMessageHandler() {
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.onEvent('walletDataReceived', (data) => {
      try {
        const walletData = JSON.parse(data);
        if (walletData && walletData.address) {
          handleWalletConnection(walletData);
        }
      } catch (e) {
        console.error('Error parsing wallet data:', e);
      }
    });
  }
  
  // Listen for messages from TON Connect
  window.addEventListener('message', (event) => {
    if (event.data.type === 'ton_connect_connection') {
      updateWalletUI(true, event.data.address);
    }
  });
}

// Initialize user data
function initUserData() {
  if (!userData) return;
  
  const username = document.getElementById('username');
  const menuUsername = document.getElementById('menu-username');
  const gcBalance = document.getElementById('gc-balance');
  const menuBalance = document.getElementById('menu-balance');
  const withdrawalProgress = document.getElementById('withdrawal-progress');
  const progressText = document.getElementById('progress-text');
  const requestWithdrawal = document.getElementById('request-withdrawal');
  
  if (username) username.textContent = userData.username;
  if (menuUsername) menuUsername.textContent = userData.username;
  if (gcBalance) gcBalance.textContent = `${userData.gameCoins.toLocaleString()} GC`;
  if (menuBalance) menuBalance.textContent = `${userData.gameCoins.toLocaleString()} GC`;
  
  // Update withdrawal progress
  if (withdrawalProgress && progressText) {
    const progressPercent = (userData.gameCoins / 200000) * 100;
    withdrawalProgress.style.width = `${Math.min(progressPercent, 100)}%`;
    progressText.textContent = `${userData.gameCoins.toLocaleString()} / 200,000 GC`;
  }
  
  // Enable withdrawal button if threshold reached
  if (requestWithdrawal && userData.gameCoins >= 200000) {
    requestWithdrawal.disabled = false;
    requestWithdrawal.textContent = "Request Withdrawal (100 TON)";
  }
}

// Load user data from server
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
      
      // Update userData
      userData.gameCoins = data.game_coins;
      initUserData();
    }
  })
  .catch(error => {
    console.error('Error loading user data:', error);
  });
}

// Switch pages
function switchPage(pageId) {
  // Hide all pages
  const pages = document.querySelectorAll('.page');
  pages.forEach(page => {
    page.classList.remove('active');
  });
  
  // Show selected page
  const targetPage = document.getElementById(`${pageId}-page`);
  if (targetPage) {
    targetPage.classList.add('active');
  }
  
  // Update active nav item
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.classList.remove('active');
    if (item.getAttribute('data-page') === pageId) {
      item.classList.add('active');
    }
  });
  
  // Load page-specific data
  loadPageData(pageId);
  
  // Load referrals page if needed
  if (pageId === 'referrals') {
    loadReferralPage();
  }
}

// Load page-specific data
function loadPageData(pageId) {
  switch (pageId) {
    case 'home':
      loadHomeData();
      break;
    case 'watch':
      loadWatchData();
      break;
    case 'wallet':
      loadWalletData();
      break;
    case 'games':
      loadGamesData();
      break;
    case 'quests':
      loadQuestsData();
      break;
    case 'otc':
      loadOtcData();
      break;
    case 'referrals':
      loadReferralsData();
      break;
    case 'shop':
      loadShopData();
      break;
  }
}

// Load home page data
async function loadHomeData() {
  try {
    const response = await fetch('/api/home/data', {
      headers: {
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        updateHomeUI(data);
      }
    }
  } catch (error) {
    console.error('Error loading home data:', error);
  }
}

// Update home UI with data
function updateHomeUI(data) {
  // Update bonus popup
  const bonusPopup = document.getElementById('daily-bonus-popup');
  if (bonusPopup) {
    bonusPopup.style.display = data.bonus_available ? 'block' : 'none';
  }
  
  // Update click counter
  const clickCount = document.getElementById('click-count');
  if (clickCount) {
    clickCount.textContent = `${data.user_data.clicks_today}/${data.user_data.click_limit}`;
  }
  
  // Update featured games
  const gamesGrid = document.querySelector('.game-grid');
  if (gamesGrid && data.featured_games) {
    gamesGrid.innerHTML = '';
    
    data.featured_games.forEach(game => {
      const gameCard = document.createElement('div');
      gameCard.className = 'game-card';
      gameCard.dataset.gameId = game.id;
      gameCard.innerHTML = `
        <div class="game-icon">${game.icon}</div>
        <div class="game-name">${game.name}</div>
      `;
      
      gameCard.addEventListener('click', () => {
        launchGame(game.id);
      });
      
      gamesGrid.appendChild(gameCard);
    });
  }
}

// Claim daily bonus
async function claimDailyBonus() {
  try {
    const response = await fetch('/api/home/claim-bonus', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        // Update UI
        const bonusPopup = document.getElementById('daily-bonus-popup');
        if (bonusPopup) bonusPopup.style.display = 'none';
        
        const gcBalance = document.getElementById('gc-balance');
        if (gcBalance) gcBalance.textContent = data.new_balance;
        
        // Update userData
        userData.gameCoins = data.new_balance;
        
        // Show success message
        if (window.Telegram && Telegram.WebApp) {
          Telegram.WebApp.showPopup({
            title: 'Bonus Claimed!',
            message: `You received ${data.bonus_amount} GC`,
            buttons: [{type: 'ok'}]
          });
        }
        
        // Save claim date to localStorage
        localStorage.setItem('lastBonusClaim', new Date().toDateString());
        
        // Reload navigation status to update notifications
        loadNavigationStatus();
      }
    }
  } catch (error) {
    console.error('Error claiming bonus:', error);
  }
}

// Handle click game
function handleClick() {
  if (!userData) return;
  
  clickCountValue++;
  const clickCount = document.getElementById('click-count');
  if (clickCount) {
    clickCount.textContent = clickCountValue;
  }
  
  // Award GC every 10 clicks
  if (clickCountValue % 10 === 0) {
    userData.gameCoins += 1;
    initUserData();
    
    // Show floating +1 GC animation
    const clickButton = document.getElementById('click-button');
    if (clickButton) {
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
  
  // Save click count to server
  fetch('/api/user/click', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
    },
    body: JSON.stringify({
      user_id: userData.user_id,
      clicks: clickCountValue
    })
  }).catch(err => console.error('Error saving clicks:', err));
}

// Load games
async function loadGames() {
  try {
    const response = await fetch('/api/games/list', {
      headers: {
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });

    if (response.ok) {
      const games = await response.json();
      renderGames(games);
    } else {
      console.error('Failed to load games');
    }
  } catch (error) {
    console.error('Failed to load games:', error);
    if (window.Telegram && Telegram.WebApp) {
      Telegram.WebApp.showAlert('Failed to load games. Please try again later.');
    }
  }
}

// Render games in grid
function renderGames(games) {
  const gamesContainer = document.getElementById('games-container');
  if (!gamesContainer) return;
  
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
      if (window.Telegram && Telegram.WebApp) {
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
                'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
              },
              body: JSON.stringify({ game_id: game.id })
            }).catch(err => console.error('Error tracking game start:', err));
            
            launchGame(game.id);
          }
        });
      }
    });
    
    gamesContainer.appendChild(gameCard);
  });
}

// Launch a game
async function launchGame(gameId) {
  try {
    const response = await fetch(`/api/games/launch/${gameId}?user_id=${userData.user_id}`, {
      headers: {
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });
    
    if (response.ok) {
      const result = await response.json();
      if (result.success) {
        // For HTML5 games, redirect to their page
        if (gameId === 'pool' || gameId === 'chess' || gameId === 'poker') {
          window.location.href = `/static/${gameId}/index.html`;
        } else {
          window.location.href = result.url;
        }
      } else {
        console.error('Failed to launch game:', result.error);
      }
    } else {
      console.error('Failed to launch game');
    }
  } catch (error) {
    console.error('Error launching game:', error);
  }
}

// Purchase item
async function purchaseItem(itemId, price) {
  // First check if user has enough GC
  if (userData.gameCoins < price) {
    // If not, offer to buy with Telegram Stars
    const starsRequired = price * 10; // Example conversion rate
    
    Telegram.WebApp.showPopup({
      title: 'Insufficient GC',
      message: `You need ${price} GC. Buy with ${starsRequired} Telegram Stars?`,
      buttons: [
        { id: 'cancel', type: 'cancel', text: 'Cancel' },
        { id: 'buy', type: 'default', text: 'Buy with Stars' }
      ]
    }, (buttonId) => {
      if (buttonId === 'buy') {
        // Open Telegram invoice for Stars payment
        openTelegramInvoice(`item_${itemId}_${starsRequired}`);
      }
    });
    return;
  }
  
  // Existing GC purchase logic
  try {
    const response = await fetch('/api/shop/purchase', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      },
      body: JSON.stringify({
        user_id: userData.user_id,
        item_id: itemId,
        price: price
      })
    });

    if (response.ok) {
      const result = await response.json();
      userData.gameCoins = result.new_balance;
      initUserData();
      Telegram.WebApp.showPopup({
        title: 'Purchase Successful',
        message: `You've successfully purchased the item!`,
        buttons: [{ type: 'default', text: 'OK' }]
      });
    }
  } catch (error) {
    console.error('Error purchasing item:', error);
  }
}

// Handle OTC swap
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

// Process exchange
function processExchange(amount, currency, paymentDetails) {
  fetch('/api/otc/swap', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
    },
    body: JSON.stringify({
      user_id: userData.user_id,
      amount: amount,
      currency: currency,
      payment_details: paymentDetails
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      Telegram.WebApp.showPopup({
        title: 'Exchange Requested',
        message: data.message,
        buttons: [{type: 'ok'}]
      });
      
      // Update user balance
      userData.gameCoins = data.new_balance;
      initUserData();
    } else {
      Telegram.WebApp.showAlert(`Exchange failed: ${data.error}`);
    }
  })
  .catch(error => {
    console.error('Error processing exchange:', error);
    Telegram.WebApp.showAlert('Exchange failed. Please try again.');
  });
}

// Social media quest functions
function openSocial(platform) {
  const urls = {
    'instagram': 'https://instagram.com/cryptogamer',
    'facebook': 'https://facebook.com/cryptogamer',
    'twitter': 'https://twitter.com/cryptogamer'
  };
  
  window.open(urls[platform], '_blank');
  
  // Show verification input after a delay
  setTimeout(() => {
    Telegram.WebApp.showPopup({
      title: `Verify ${platform} follow`,
      message: 'Enter the verification code posted on our profile:',
      buttons: [
        {id: 'cancel', type: 'cancel', text: 'Cancel'},
        {id: 'verify', type: 'default', text: 'Verify'}
      ]
    }, (btnId) => {
      if (btnId === 'verify') {
        const verificationCode = prompt('Enter verification code:');
        if (verificationCode) {
          verifyQuest(`follow_${platform}`, {verification_code: verificationCode});
        }
      }
    });
  }, 5000);
}

function joinChannel() {
  window.open('https://t.me/cryptogamer_channel', '_blank');
  
  setTimeout(() => {
    Telegram.WebApp.showPopup({
      title: 'Verify channel join',
      message: 'Enter the verification code posted in the channel:',
      buttons: [
        {id: 'cancel', type: 'cancel', text: 'Cancel'},
        {id: 'verify', type: 'default', text: 'Verify'}
      ]
    }, (btnId) => {
      if (btnId === 'verify') {
        const verificationCode = prompt('Enter verification code:');
        if (verificationCode) {
          verifyQuest('join_telegram_channel', {verification_code: verificationCode});
        }
      }
    });
  }, 5000);
}

function postOnTwitter() {
  const text = encodeURIComponent('Check out CryptoGamer - Earn TON coins while playing games! 🎮💰 #CryptoGamer #TON');
  window.open(`https://twitter.com/intent/tweet?text=${text}`, '_blank');
  
  setTimeout(() => {
    const tweetUrl = prompt('Please paste the URL of your tweet:');
    if (tweetUrl && tweetUrl.includes('twitter.com')) {
      verifyQuest('post_twitter', {post_url: tweetUrl});
    }
  }, 10000);
}

function retweetPost() {
  window.open('https://twitter.com/cryptogamer/status/1234567890', '_blank');
  
  setTimeout(() => {
    const retweetUrl = prompt('Please paste the URL of your retweet:');
    if (retweetUrl && retweetUrl.includes('twitter.com')) {
      verifyQuest('retweet_post', {retweet_url: retweetUrl});
    }
  }, 10000);
}

function postTikTok() {
  Telegram.WebApp.showAlert('Post a TikTok video about CryptoGamer and tag us @cryptogamer. Then return here to verify.');
  
  setTimeout(() => {
    const videoUrl = prompt('Please paste the URL of your TikTok video:');
    if (videoUrl && videoUrl.includes('tiktok.com')) {
      verifyQuest('post_tikTok', {post_url: videoUrl});
    }
  }, 30000);
}

// Binance quest functions
function openBinance() {
  window.open('https://accounts.binance.com/register?ref=CRYPTOGAMER', '_blank');
  
  setTimeout(() => {
    const binanceId = prompt('Enter your Binance ID (username or email):');
    if (binanceId) {
      verifyQuest('signup_binance', {
        binance_id: binanceId,
        used_referral: 'CRYPTOGAMER'
      });
    }
  }, 60000);
}

function shareBinance() {
  Telegram.WebApp.showAlert('Share your Binance referral link with friends. When someone signs up, come back here to verify.');
  
  setTimeout(() => {
    const referralCount = prompt('How many friends signed up using your referral?');
    if (referralCount && parseInt(referralCount) > 0) {
      verifyQuest('invite_binance_trader', {referral_count: parseInt(referralCount)});
    }
  }, 30000);
}

// General quest function
function verifyQuest(questType, evidence = {}) {
  evidence.user_id = userData.user_id;
  
  fetch('/api/quests/verify', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
    },
    body: JSON.stringify({
      quest_type: questType,
      evidence: evidence
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      Telegram.WebApp.showPopup({
        title: 'Quest Completed!',
        message: `You earned ${data.reward} GC!`,
        buttons: [{type: 'ok'}]
      });
      loadUserData(); // Refresh user data
    } else {
      Telegram.WebApp.showAlert(`Verification failed: ${data.error}`);
    }
  })
  .catch(error => {
    console.error('Error verifying quest:', error);
    Telegram.WebApp.showAlert('Failed to verify quest. Please try again.');
  });
}

function startSocialCycle() {
  Telegram.WebApp.showAlert('Complete this social cycle: 1. Post about us 2. Retweet our post 3. Earn from engagement 4. Repeat the process. Then come back to verify.');
  
  setTimeout(() => {
    verifyQuest('post_retweet_earn_repeat', {
      posted: true,
      retweeted: true,
      earned: true,
      repeated: true
    });
  }, 30000);
}

// Load shop items
function loadShopItems() {
  fetch('/api/shop/items')
    .then(response => response.json())
    .then(items => {
      const shopContainer = document.querySelector('.shop-items-mini');
      if (!shopContainer) return;
      
      shopContainer.innerHTML = '';
      
      items.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'shop-item-mini';
        itemElement.innerHTML = `
          <div class="item-header-mini">${item.name}</div>
          <div class="item-icon-mini">${getItemIcon(item.id)}</div>
          <div class="item-price-mini">${item.price} GC</div>
          <button class="btn-buy-mini" data-item="${item.id}">Buy</button>
        `;
        
        itemElement.querySelector('.btn-buy-mini').addEventListener('click', () => {
          purchaseItem(item.id, item.price);
        });
        
        shopContainer.appendChild(itemElement);
      });
    })
    .catch(error => {
      console.error('Failed to load shop items:', error);
    });
}

// Get item icon
function getItemIcon(itemId) {
  const icons = {
    'global_booster': '🚀',
    'trivia_extra_time': '⏱️',
    'spin_extra_spin': '🎡',
    'clicker_auto_upgrade': '🤖'
  };
  return icons[itemId] || '🎁';
}

// Load referral page
function loadReferralPage() {
  fetch('/games/static/referrals/index.html')
    .then(response => response.text())
    .then(html => {
      const referralsPage = document.getElementById('referrals-page');
      if (referralsPage) {
        referralsPage.innerHTML = html;
        initReferralPage();
      }
    })
    .catch(error => {
      console.error('Error loading referral page:', error);
    });
}

// Initialize referral page
function initReferralPage() {
  // Initialize the referral page
  if (typeof loadAffiliateStats === 'function') {
    loadAffiliateStats();
  }
}

// Request withdrawal
function requestWithdrawalFunc() {
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.showPopup({
      title: "Withdrawal Request",
      message: "Your request to withdraw 100 TON has been submitted. It will be processed within 24 hours.",
      buttons: [{ type: "default", text: "OK" }]
    });
  }
}

// Copy referral link
function copyReferralLink() {
  const referralLink = document.getElementById('referral-link');
  if (referralLink) {
    referralLink.select();
    document.execCommand('copy');
    
    if (window.Telegram && Telegram.WebApp) {
      Telegram.WebApp.showPopup({
        title: "Copied!",
        message: "Referral link copied to clipboard",
        buttons: [{ type: 'default', text: 'OK' }]
      });
    }
  }
}

// Switch tabs
function switchTab(tabId) {
  const tabPanes = document.querySelectorAll('.tab-pane');
  const tabBtns = document.querySelectorAll('.tab-btn');
  
  tabPanes.forEach(pane => {
    pane.classList.remove('active');
  });
  
  tabBtns.forEach(btn => {
    btn.classList.remove('active');
  });
  
  const targetTab = document.getElementById(`${tabId}-tab`);
  const targetBtn = document.querySelector(`[data-tab="${tabId}"]`);
  
  if (targetTab) targetTab.classList.add('active');
  if (targetBtn) targetBtn.classList.add('active');
}

// Initialize navigation
async function initNavigation() {
  try {
    const response = await fetch('/api/navigation/pages', {
      headers: {
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        updateNavigationUI(data.pages);
      }
    }
  } catch (error) {
    console.error('Error initializing navigation:', error);
  }
}

// Update navigation UI
function updateNavigationUI(pages) {
  const navContainer = document.querySelector('.bottom-nav');
  if (!navContainer) return;
  
  // Clear existing navigation
  navContainer.innerHTML = '';
  
  // Add navigation items
  pages.forEach(page => {
    if (page.floating) return; // Skip floating items (handled separately)
    
    const navItem = document.createElement('a');
    navItem.href = '#';
    navItem.className = 'nav-item';
    navItem.dataset.page = page.id;
    navItem.innerHTML = `
      <span class="nav-icon">${page.icon}</span>
      <span class="nav-label">${page.name}</span>
    `;
    
    navItem.addEventListener('click', (e) => {
      e.preventDefault();
      switchPage(page.id);
    });
    
    navContainer.appendChild(navItem);
  });
}

// Load navigation status (notifications)
async function loadNavigationStatus() {
  try {
    const response = await fetch('/api/navigation/status', {
      headers: {
        'X-Telegram-InitData': window.Telegram ? Telegram.WebApp.initData : ''
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        updateNotificationBadges(data.notifications);
      }
    }
  } catch (error) {
    console.error('Error loading navigation status:', error);
  }
}

// Update notification badges
function updateNotificationBadges(notifications) {
  const navItems = document.querySelectorAll('.nav-item');
  
  navItems.forEach(item => {
    const pageId = item.dataset.page;
    const hasNotification = notifications[pageId];
    
    // Remove existing badge
    const existingBadge = item.querySelector('.notification-badge');
    if (existingBadge) {
      existingBadge.remove();
    }
    
    // Add new badge if needed
    if (hasNotification) {
      const badge = document.createElement('span');
      badge.className = 'notification-badge';
      badge.textContent = '';
      item.appendChild(badge);
    }
  });
}

// Add affiliate program initialization
function initAffiliateProgram() {
  // Check if user is already an affiliate
  fetch('/api/affiliate/status', {
    headers: {
      'X-Telegram-InitData': window.Telegram.WebApp.initData
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.is_affiliate) {
      // Show affiliate stats in profile
      const profileStats = document.getElementById('profile-stats');
      if (profileStats) {
        const affiliateStats = `
          <div class="profile-stat">
            <span>Referrals:</span>
            <span>${data.referral_count}</span>
          </div>
          <div class="profile-stat">
            <span>Earnings:</span>
            <span>${data.earnings} Stars</span>
          </div>
        `;
        profileStats.innerHTML += affiliateStats;
      }
    }
  })
  .catch(err => console.error('Error loading affiliate status:', err));
}

// Handle wallet errors
function handleWalletError(error) {
  console.error('Wallet error:', error);
  
  let message = 'Wallet operation failed';
  if (error.message.includes('user rejected')) {
    message = 'Transaction cancelled by user';
  } else if (error.message.includes('insufficient funds')) {
    message = 'Insufficient balance';
  }
  
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.showPopup({
      title: 'Error',
      message: message,
      buttons: [{type: 'ok'}]
    });
  }
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
  
  .notification-badge {
    position: absolute;
    top: -5px;
    right: -5px;
    width: 10px;
    height: 10px;
    background-color: #ff4757;
    border-radius: 50%;
  }
`;
document.head.appendChild(style);

// Simulate wallet connection event for demonstration
setTimeout(() => {
  window.postMessage({ 
    type: 'wallet_connected', 
    address: 'EQDrjaMAd1uyVtVb1hECV3a6F5Kc_ZLrjV7lLp7DZqNJiA1D' 
  }, '*');
}, 2000);