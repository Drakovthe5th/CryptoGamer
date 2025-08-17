// miniapp.js - Core Mini App functionality
const MAX_RESETS = 3;
let userData = {
  id: null,
  username: 'Guest',
  balance: 0,
  clicks: 0,
  referrals: 0,
  refEarnings: 0,
  bonusClaimed: false,
  gameCoins: 0
};

class Miniapp {
  static init(telegramInitData) {
    this.initData = telegramInitData;
    this.securityToken = this.generateSecurityToken();
    this.userData = userData;
  }

  static generateSecurityToken() {
    const token = Math.random().toString(36).substring(2, 15);
    const timestamp = Math.floor(Date.now() / 1000);
    return btoa(`${token}:${timestamp}`);
  }

  static async apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
      'X-Telegram-Init-Data': this.initData,
      'X-Security-Token': this.securityToken
    };
    
    if (body) {
      headers['Content-Type'] = 'application/json';
    }
    
    try {
      const options = {
        method,
        headers,
        credentials: 'include'
      };
      
      if (body) {
        options.body = JSON.stringify(body);
      }
      
      const response = await fetch(endpoint, options);
      
      if (response.status === 403) {
        document.getElementById('security-alert').style.display = 'block';
        Telegram.WebApp.showAlert('Account restricted. Contact support.');
        return null;
      }
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'API request failed');
      }
      
      return await response.json();
    } catch (error) {
      Telegram.WebApp.showAlert(error.message || 'Request failed');
      throw error;
    }
  }

  static async loadUserData() {
    try {
      const response = await this.apiRequest(`/api/user/secure-data?user_id=${this.userData.id}`);
      if (response && response.token) {
        const userData = this.parseJwt(response.token);
        this.userData = {
          ...this.userData,
          username: userData.username,
          balance: userData.balance,
          clicks: userData.clicks_today,
          referrals: userData.referrals,
          refEarnings: userData.ref_earnings,
          bonusClaimed: userData.bonus_claimed,
          gameCoins: userData.game_coins
        };
        this.updateUI();
      }
    } catch (error) {
      console.error('Failed to load user data:', error);
    }
  }

  static parseJwt(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => 
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));

      return JSON.parse(jsonPayload);
    } catch (e) {
      return null;
    }
  }

  static updateUI() {
    document.querySelectorAll('#balance, #wallet-balance, #profile-balance').forEach(el => {
      el.textContent = this.userData.balance.toFixed(6) + ' TON';
    });
    
    document.getElementById('click-count').textContent = this.userData.clicks;
    document.getElementById('quest-ads').textContent = "0";
    document.getElementById('quest-invite').textContent = this.userData.referrals > 0 ? "1" : "0";
    document.getElementById('ref-count').textContent = this.userData.referrals;
    document.getElementById('ref-earnings').textContent = this.userData.refEarnings.toFixed(6) + ' TON';
    
    document.querySelectorAll('#profile-username, #profile-name').forEach(el => {
      el.textContent = this.userData.username;
    });
    
    const bonusBtn = document.getElementById('bonus-btn');
    if (bonusBtn) {
      if (this.userData.bonusClaimed) {
        bonusBtn.textContent = '✅ Bonus Claimed';
        bonusBtn.disabled = true;
      } else {
        bonusBtn.textContent = '🎁 Claim 0.05 TON';
        bonusBtn.disabled = false;
      }
    }

    document.querySelectorAll('#gc-display, #gc-balance').forEach(el => {
      el.textContent = `${this.userData.gameCoins} GC`;
    });

    const tonEquivalent = document.getElementById('ton-equivalent');
    if (tonEquivalent) {
      tonEquivalent.textContent = (this.userData.gameCoins / 2000).toFixed(6) + ' TON';
    }
  }

  static async claimDailyBonus() {
    try {
      const response = await this.apiRequest('/api/quests/claim_bonus', 'POST', {
        user_id: this.userData.id
      });
      
      if (response && response.success) {
        this.userData.balance = response.new_balance;
        this.userData.bonusClaimed = true;
        this.updateUI();
        
        Telegram.WebApp.showPopup({
          title: 'Bonus Claimed!', 
          message: '+0.05 TON added to your balance',
          buttons: [{id: 'ok', type: 'ok'}]
        });
      }
    } catch (error) {
      console.error('Failed to claim bonus:', error);
      Telegram.WebApp.showPopup({
        title: 'Error', 
        message: 'Failed to claim bonus. Please try again.',
        buttons: [{id: 'ok', type: 'ok'}]
      });
    }
  }

  static async earnFromClick() {
    try {
      if (this.userData.clicks >= 100) {
        Telegram.WebApp.showPopup({
          title: 'Limit Reached!',
          message: 'Try again tomorrow',
          buttons: [{id: 'ok', type: 'ok'}]
        });
        return;
      }
      
      const response = await this.apiRequest('/api/quests/record_click', 'POST', {
        user_id: this.userData.id
      });
      
      if (response) {
        this.userData.clicks = response.clicks;
        this.userData.balance = response.balance;
        this.updateUI();
        
        const clickArea = document.querySelector('.click-area');
        if (clickArea) {
          clickArea.style.transform = 'scale(0.95)';
          setTimeout(() => clickArea.style.transform = 'scale(1)', 120);
          
          const reward = document.createElement('div');
          reward.className = 'click-reward';
          reward.textContent = '+0.0001 TON';
          clickArea.appendChild(reward);
          setTimeout(() => reward.remove(), 1000);
        }
      }
    } catch (error) {
      console.error('Failed to record click:', error);
      Telegram.WebApp.showPopup({
        title: 'Error', 
        message: 'Failed to record click. Please try again.',
        buttons: [{id: 'ok', type: 'ok'}]
      });
    }
  }

  static async rewardedInterstitial() {
    try {
      await show_9644715();
      
      const response = await this.apiRequest('/api/ads/reward', 'POST', {
        user_id: this.userData.id,
        ad_id: 'monetag_9644715'
      });
      
      if (response) {
        this.userData.balance = response.new_balance;
        this.updateUI();
        
        Telegram.WebApp.showPopup({
          title: 'Ad Watched!', 
          message: `+${response.reward.toFixed(6)} TON added to your balance`,
          buttons: [{id: 'ok', type: 'ok'}]
        });
      }
    } catch (error) {
      console.error('Failed to show ad:', error);
      Telegram.WebApp.showPopup({
        title: 'Ad Error', 
        message: 'Failed to show ad. Please try again.',
        buttons: [{id: 'ok', type: 'ok'}]
      });
    }
  }

  static async generateReferralLink() {
    try {
      const response = await this.apiRequest(`/api/referral/generate?user_id=${this.userData.id}`);
      if (response && response.success) {
        document.getElementById('ref-link').textContent = response.referral_link;
        return response.referral_link;
      }
    } catch (error) {
      console.error('Failed to generate referral:', error);
    }
    return null;
  }

  static async getReferralStats() {
    try {
      const response = await this.apiRequest(`/api/referral/stats?user_id=${this.userData.id}`);
      if (response && response.success) {
        this.userData.referrals = response.referrals;
        this.userData.refEarnings = response.ref_earnings;
        this.updateUI();
      }
    } catch (error) {
      console.error('Failed to get referral stats:', error);
    }
  }

  static async getOTCRates() {
    try {
      const response = await this.apiRequest('/api/otc/rates');
      if (response && response.success) {
        return response.rates;
      }
    } catch (error) {
      console.error('Failed to get OTC rates:', error);
    }
    return null;
  }

  static async createStaking(amount) {
    try {
      const response = await this.apiRequest('/api/staking/create', 'POST', {
        user_id: this.userData.id,
        amount: amount
      });
      
      if (response && response.success) {
        Telegram.WebApp.showPopup({
          title: 'Staking Created!', 
          message: `${amount} TON staked successfully`,
          buttons: [{id: 'ok', type: 'ok'}]
        });
        return true;
      }
    } catch (error) {
      console.error('Failed to create staking:', error);
    }
    return false;
  }

  static async launchGame(gameId) {
      try {
          const response = await this.apiRequest(`/api/games/token?game=${gameId}`);
          
          if (response?.token) {
              const gameUrl = `/games/${gameId}?user_id=${this.userData.id}&token=${response.token}`;
              document.getElementById('game-iframe').src = gameUrl;
              document.getElementById('game-iframe-page').style.display = 'block';
              
              await this.apiRequest('/api/game/start', 'POST', {
                  game_id: gameId
              });
          }
      } catch (error) {
          console.error('Failed to launch game:', error);
          Telegram.WebApp.showAlert('Game failed to load. Please try again.');
      }
  }

  static async convertGC(gcAmount) {
    try {
      const response = await this.apiRequest('/api/convert/gc-to-ton', 'POST', {
        gc_amount: gcAmount
      });
      
      if (response && response.success) {
        return response;
      }
    } catch (error) {
      console.error('Conversion failed:', error);
      this.showToast('Failed to convert game coins', 'error');
    }
    return null;
  }

  static showToast(message, type = 'success') {
    Telegram.WebApp.showPopup({
      title: type === 'error' ? 'Error' : 'Success',
      message: message,
      buttons: [{id: 'ok', type: 'ok'}]
    });
  }

  static async purchaseItem(itemId) {
    try {
      const response = await this.apiRequest('/api/shop/purchase', 'POST', {
        user_id: this.userData.id,
        item_id: itemId
      });
      
      if (response && response.success) {
        this.userData.gameCoins = response.new_gc_balance;
        this.updateUI();
        
        Telegram.WebApp.showPopup({
          title: 'Purchase Successful!', 
          message: `You bought ${this.getItemName(itemId)}`,
          buttons: [{id: 'ok', type: 'ok'}]
        });
        
        return true;
      }
    } catch (error) {
      console.error('Purchase failed:', error);
      this.showToast('Not enough coins or item unavailable', 'error');
    }
    return false;
  }

  static getItemName(itemId) {
    const items = {
      'global_booster': '2x Earnings Booster',
      'trivia_extra_time': 'Trivia Time Extender',
      'spin_extra_spin': 'Extra Spin',
      'clicker_auto_upgrade': 'Auto-Clicker'
    };
    return items[itemId] || 'Item';
  }

  static connectWallet() {
    if (typeof window.ton === 'undefined') {
      alert("TON Wallet not available");
      return;
    }
    
    window.ton.send("ton_requestWallets").then(wallets => {
      if (wallets.length > 0) {
        const address = wallets[0].address;
        Telegram.WebApp.sendData(JSON.stringify({
          type: 'connect_wallet',
          address: address
        }));
        updateWalletStatus(true, address);
      }
    });
  }

    // ADD to Miniapp class
  static async getGameSessionData(sessionId) {
      try {
          const response = await this.apiRequest(`/api/game/session/${sessionId}`);
          return response;
      } catch (error) {
          console.error('Failed to get session data:', error);
          return null;
      }
  }

  static async submitGameResults(gameId, score, sessionId) {
      try {
          const response = await this.apiRequest('/api/game/complete', 'POST', {
              game_id: gameId,
              score: score,
              session_id: sessionId
          });
          
          if (response && response.success) {
              this.userData.gameCoins = response.new_gc_balance;
              this.updateUI();
              return true;
          }
          return false;
      } catch (error) {
          console.error('Failed to submit game results:', error);
          return false;
      }
  }

  static async getBoosters() {
      try {
          const response = await this.apiRequest('/api/boosters/active');
          return response.boosters || [];
      } catch (error) {
          console.error('Failed to get boosters:', error);
          return [];
      }
  }

}

// Helper functions
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(page => {
    page.classList.remove('active');
  });
  document.getElementById(`${pageId}-page`).classList.add('active');
  
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  document.querySelector(`.nav-btn[data-page="${pageId}"]`).classList.add('active');
}

function hideGame() {
  document.getElementById('game-iframe-page').style.display = 'none';
  document.getElementById('game-iframe').src = '';
}

function updateWalletStatus(connected, address = '') {
    const indicator = document.getElementById('wallet-indicator');
    const addressEl = document.getElementById('wallet-address');
    
    if (connected) {
        indicator.textContent = '🟢';
        addressEl.textContent = address.substring(0, 6) + '...' + address.substring(address.length - 4);
    } else {
        indicator.textContent = '🔴';
        addressEl.textContent = 'Not connected';
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    
    Miniapp.init(tg.initData);
    Miniapp.userData.id = tg.initDataUnsafe.user?.id;

    if (!Miniapp.userData.id) {
      throw new Error('User ID missing');
    }
    
    await Miniapp.loadUserData();
    await Miniapp.generateReferralLink();
    await Miniapp.getReferralStats();

    // Check wallet connection
    const userData = await Miniapp.loadUserData();
    if (userData && userData.wallet_address) {
        updateWalletStatus(true, userData.wallet_address);
    }

    const rates = await Miniapp.getOTCRates();
    if (rates) {
      document.getElementById('rate-usd').textContent = `$${rates.USD}`;
      document.getElementById('rate-kes').textContent = rates.KES;
      document.getElementById('rate-eur').textContent = `€${rates.EUR}`;
      document.getElementById('rate-usdt').textContent = rates.USDT;
    }
    
    tg.showPopup({
      title: 'Welcome!', 
      message: `Let's earn TON, ${Miniapp.userData.username}!`,
      buttons: [{id: 'ok', type: 'ok'}]
    });
    
    // Setup event handlers
    document.getElementById('bonus-btn').addEventListener('click', () => Miniapp.claimDailyBonus());
    document.querySelector('.click-area')?.addEventListener('click', () => Miniapp.earnFromClick());
    document.getElementById('watch-ad-btn')?.addEventListener('click', () => Miniapp.rewardedInterstitial());
    document.getElementById('staking-btn')?.addEventListener('click', () => Miniapp.createStaking(5));
    document.getElementById('copy-ref-btn')?.addEventListener('click', () => {
      navigator.clipboard.writeText(document.getElementById('ref-link').textContent);
      tg.showPopup({
        title: 'Copied', 
        message: 'Referral link copied',
        buttons: [{id: 'ok', type: 'ok'}]
      });
    });
    document.getElementById('convert-gc-btn')?.addEventListener('click', () => {
      const gcInput = document.getElementById('gc-amount');
      const gcValue = parseFloat(gcInput.value);
      
      if (isNaN(gcValue)) {
        Miniapp.showToast('Please enter a valid number', 'error');
        return;
      }

      Miniapp.convertGC(gcValue).then(response => {
        if (response) {
          const resultDiv = document.getElementById('conversion-result');
          const resultText = document.getElementById('conversion-result-text');
        
          resultText.innerHTML = `
            ${gcValue.toLocaleString()} GC = <strong>${response.ton_amount.toFixed(6)} TON</strong><br>
            <small>Exchange rate: ${response.conversion_rate} GC = 1 TON</small>
          `;
          resultDiv.style.display = 'block';
        }
      });
    });
    document.getElementById('share-app-btn')?.addEventListener('click', () => {
      Telegram.WebApp.shareUrl(
        'https://t.me/CryptoGameMinerBot',
        'Earn TON coins by playing games!'
      );
    });
    document.getElementById('swap-ton-btn')?.addEventListener('click', () => {
      Miniapp.showToast('Exchange started', 'success');
    });
    document.getElementById('quest-bonus-btn')?.addEventListener('click', () => {
      Miniapp.claimDailyBonus();
    });
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        showPage(this.dataset.page);
      });
    });
    
    document.querySelectorAll('.game-card').forEach(card => {
      card.addEventListener('click', function() {
        const gameId = this.dataset.gameId;
        Miniapp.launchGame(gameId);
      });
    });

    document.querySelectorAll('.purchase-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.dataset.itemId;
            Miniapp.purchaseItem(itemId).then(success => {
                if (success) {
                    Telegram.WebApp.showPopup({
                        title: 'Purchase Complete!',
                        message: `You've purchased ${itemId}`,
                        buttons: [{type: 'ok'}]
                    });
                }
            });
        });
    });
    
    // Close game button
    document.getElementById('close-game-btn').addEventListener('click', hideGame);
    
  } catch (error) {
    console.error('Initialization failed:', error);
    Telegram.WebApp.showAlert('Failed to initialize app. Please try again.');
  }
});

// Handle wallet connection response
Telegram.WebApp.onEvent('wallet_connected', (eventData) => {
  if (eventData.address) {
    updateWalletStatus(true, eventData.address);
    Telegram.WebApp.showAlert('Wallet connected successfully!');
  }
});