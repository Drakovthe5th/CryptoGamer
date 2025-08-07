// Claim daily bonus
function claimDailyBonus() {
  if (!window.userData) return;
  window.userData.balance += 0.05;
  updateBalance();
  window.Telegram.WebApp.showPopup({
    title: 'Daily Bonus Claimed!',
    message: 'You received 0.05 TON',
    buttons: [{ id: 'ok', type: 'ok' }]
  });
}

// Click-to-earn game
function earnFromClick() {
  if (!window.userData) return;
  if (window.userData.clicks < 100) {
    window.userData.clicks++;
    window.userData.balance += 0.01;
    updateBalance();
    document.getElementById('click-count').textContent = window.userData.clicks;
    // brief click animation
    const clickArea = document.querySelector('.click-area');
    clickArea.style.transform = 'scale(0.95)';
    setTimeout(() => clickArea.style.transform = 'scale(1)', 100);
  } else {
    window.Telegram.WebApp.showPopup({
      title: 'Daily Limit Reached',
      message: 'Come back tomorrow for more clicks!',
      buttons: [{ id: 'ok', type: 'ok' }]
    });
  }
}

window.userData = { balance: 0.5, clicks: 0, /* …other fields… */ };
document.addEventListener('DOMContentLoaded', () => {
  updateBalance();
  document.getElementById('click-count').textContent = window.userData.clicks;
  // show welcome popup if desired
});
