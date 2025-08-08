// 1. Conditionally inject Telegram WebApp SDK if opened inside Telegram
(function loadTelegramSDK() {
  const params = new URLSearchParams(window.location.search);
  if (params.has('tgWebAppInitData')) {
    const s = document.createElement('script');
    s.src = 'https://telegram.org/js/telegram-web-app.js';
    s.async = true;
    document.head.appendChild(s);
  }
})();

// 2. Application state
window.userData = {
  balance: 0.00,    // initial balance
  clicks: 0,        // clicks today
  maxClicks: 100    // daily cap
};

// 3. Helpers
function updateBalance() {
  document.querySelectorAll('#balance').forEach(el => {
    el.textContent = window.userData.balance.toFixed(2);
  });
}

function showPopup(options) {
  if (window.Telegram && Telegram.WebApp && Telegram.WebApp.showPopup) {
    Telegram.WebApp.showPopup(options);
  }
}

// 4. Home-page functions
function claimDailyBonus() {
  if (window.userData.bonusClaimed) return;
  window.userData.balance += 0.05;
  window.userData.bonusClaimed = true;
  updateBalance();
  showPopup({
    title: 'Daily Bonus Claimed!',
    message: 'You received 0.05 TON',
    buttons: [{ id: 'ok', type: 'ok' }]
  });
}

function earnFromClick() {
  if (window.userData.clicks >= window.userData.maxClicks) {
    return showPopup({
      title: 'Daily Limit Reached',
      message: 'Come back tomorrow for more clicks!',
      buttons: [{ id: 'ok', type: 'ok' }]
    });
  }

  window.userData.clicks++;
  window.userData.balance += 0.01;
  updateBalance();
  document.getElementById('click-count').textContent = window.userData.clicks;

  // brief shrink animation
  const clickArea = document.querySelector('.click-area');
  clickArea.style.transform = 'scale(0.95)';
  setTimeout(() => clickArea.style.transform = 'scale(1)', 100);
}

// 5. Minimal page switcher (so “Featured Games” button doesn’t break)
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(`${pageId}-page`);
  if (target) target.classList.add('active');

  // update nav buttons
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  const idx = ['home','watch','wallet','games','quests','otc','referrals'].indexOf(pageId);
  if (idx >= 0) document.querySelectorAll('.nav-btn')[idx].classList.add('active');
}

// 6. On load: init UI
document.addEventListener('DOMContentLoaded', () => {
  updateBalance();
  document.getElementById('click-count').textContent = window.userData.clicks;

  // Show welcome popup if in Telegram
  if (window.Telegram && Telegram.WebApp) {
    Telegram.WebApp.ready();
    showPopup({
      title: 'Welcome to CryptoGameMiner!',
      message: 'Start earning TON by playing games and completing quests.',
      buttons: [{ id: 'ok', type: 'ok' }]
    });
  }

  // Wire up button handlers
  document.querySelectorAll('[onclick="claimDailyBonus()"]').forEach(btn =>
    btn.addEventListener('click', claimDailyBonus)
  );
  document.querySelectorAll('[onclick="earnFromClick()"]').forEach(area =>
    area.addEventListener('click', earnFromClick)
  );
});

async function loadUserData() {
  try {
    const response = await apiRequest('/api/user/secure-data');
    if (response.token) {
      // Verify JWT server-side
      const userData = parseJwt(response.token);
      document.querySelectorAll('#balance').forEach(el => {
        el.textContent = `Balance: ${userData.balance.toFixed(6)} TON`;
      });
      // Store in session instead of global object
      sessionStorage.setItem('userData', JSON.stringify({
        id: userData.id,
        username: userData.username,
        balance: userData.balance
      }));
    }
  } catch (error) {
    console.error('Secure data load failed:', error);
  }
}
