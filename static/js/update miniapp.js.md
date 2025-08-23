1. Update /static/js/miniapp.js related to Telegram Web Events Integration for CryptoGamer

// Initialize Telegram Web Events
const telegramWebEvents = new TelegramWebEvents();

// Add this after DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
  // ... existing code ...
  
  // Initialize Web Events
  initTelegramWebEvents();
  
  // ... rest of existing code ...
});

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
      profileMenu.classList.add('active');
    });
    
    Telegram.WebApp.onEvent('invoiceClosed', (eventData) => {
      handleInvoiceClosed(eventData);
    });
  }
}

// Add these new functions for handling web events
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

function triggerHapticFeedback(type, impactStyle, notificationType) {
  telegramWebEvents.triggerHapticFeedback(type, impactStyle, notificationType);
}

function shareScore(score, game) {
  telegramWebEvents.shareScore(score, game);
}

function shareGame(game) {
  telegramWebEvents.shareGame(game);
}

function openTelegramInvoice(slug) {
  telegramWebEvents.openInvoice(slug);
}

// Modify the purchaseItem function to use Telegram Stars
async function purchaseItem(itemId, price) {
  // First check if user has enough GC
  if (currentBalance < price) {
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
        user_id: telegramUser ? telegramUser.id : 'demo',
        item_id: itemId,
        price: price
      })
    });
    
    // ... rest of existing code ...
  } catch (error) {
    console.error('Error purchasing item:', error);
  }
}


2. ##Changes to miniapp.js:## --> related to Affiliate and Invite Integration for CryptoGamer

// Add these functions to miniapp.js
function loadReferralPage() {
    fetch('/games/static/referrals/index.html')
        .then(response => response.text())
        .then(html => {
            document.getElementById('referrals-page').innerHTML = html;
            initReferralPage();
        });
}

function initReferralPage() {
    // Initialize the referral page
    if (typeof loadAffiliateStats === 'function') {
        loadAffiliateStats();
    }
}

// Add to the page switching logic
function switchPage(pageId) {
    // ... existing code ...
    
    if (pageId === 'referrals') {
        loadReferralPage();
    }
    
    // ... existing code ...
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
            document.getElementById('profile-stats').innerHTML += affiliateStats;
        }
    });
}

// Call this during initialization
document.addEventListener('DOMContentLoaded', () => {
    // ... existing code ...
    initAffiliateProgram();
});