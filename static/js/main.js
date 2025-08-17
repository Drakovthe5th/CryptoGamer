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