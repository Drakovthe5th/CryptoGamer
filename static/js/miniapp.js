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

class Miniapp {
    static initData = null;
    static securityToken = null;
    
    static init(telegramInitData) {
        this.initData = telegramInitData;
        this.securityToken = this.generateSecurityToken();
    }
    
    static generateSecurityToken() {
        const token = Math.random().toString(36).substring(2, 15);
        const timestamp = Math.floor(Date.now() / 1000);
        return btoa(`${token}:${timestamp}`);
    }
    
    static async getUserData(userId) {
        try {
            const response = await fetch(`/api/user/data?user_id=${userId}`, {
                headers: {
                    'X-Telegram-InitData': this.initData,
                    'X-Security-Token': this.securityToken
                }
            });
            
            const data = await response.json();
            
            if (data.balance !== undefined) {
                document.getElementById('balance').textContent = data.balance.toFixed(2);
            }
            
            if (data.username) {
                document.getElementById('username').textContent = data.username;
            }
            
            return data;
        } catch (error) {
            console.error('Failed to get user data:', error);
            return null;
        }
    }
    
    static async getQuests(userId) {
        try {
            const response = await fetch(`/api/quests?user_id=${userId}`, {
                headers: {
                    'X-Telegram-InitData': this.initData,
                    'X-Security-Token': this.securityToken
                }
            });
            
            const quests = await response.json();
            this.renderQuests(quests);
            return quests;
        } catch (error) {
            console.error('Failed to get quests:', error);
            return [];
        }
    }
    
    static renderQuests(quests) {
        const container = document.getElementById('quest-list');
        container.innerHTML = '';
        
        quests.forEach(quest => {
            const questElement = document.createElement('div');
            questElement.className = `quest ${quest.completed ? 'completed' : ''}`;
            questElement.innerHTML = `
                <h4>${quest.title}</h4>
                <p>${quest.description}</p>
                <div class="progress">
                    <div class="progress-bar" style="width: ${quest.progress}%"></div>
                </div>
                <div class="reward">Reward: ${quest.reward} TON</div>
                ${!quest.completed ? `<button class="btn-small" data-quest="${quest.id}">Complete</button>` : ''}
            `;
            container.appendChild(questElement);
        });
    }
    
    static async claimBonus(userId) {
        try {
            const response = await fetch('/api/quests/claim_bonus', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-InitData': this.initData,
                    'X-Security-Token': this.securityToken
                },
                body: JSON.stringify({ user_id: userId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                alert(`Bonus claimed! New balance: ${result.new_balance} TON`);
                this.getUserData(userId);
            } else {
                alert('Failed to claim bonus: ' + (result.error || 'Unknown error'));
            }
            
            return result;
        } catch (error) {
            console.error('Failed to claim bonus:', error);
            return { success: false, error: 'Network error' };
        }
    }
    
    static async recordGameCompletion(userId, gameId, score) {
        try {
            const response = await fetch('/api/game/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-InitData': this.initData,
                    'X-Security-Token': this.securityToken
                },
                body: JSON.stringify({ 
                    user_id: userId,
                    game_id: gameId,
                    score: score
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log(`Game completed! Reward: ${result.reward} TON`);
                this.getUserData(userId);
                this.getQuests(userId);
            }
            
            return result;
        } catch (error) {
            console.error('Failed to record game completion:', error);
            return { success: false, error: 'Network error' };
        }
    }
    
    static showStats(userId) {
        // This would open a stats modal or navigate to stats page
        alert('Stats feature coming soon!');
    }
    
    static initiateWithdrawal(userId) {
        // This would open a withdrawal form
        alert('Withdrawal feature coming soon!');
    }
}

// Initialize with Telegram Web App data
Miniapp.init(Telegram.WebApp.initData);

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
