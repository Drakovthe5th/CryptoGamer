// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
  // Get session ID from URL
  const sessionId = new URLSearchParams(window.location.search).get('session_id');
  
  // Get user data
  const urlParams = new URLSearchParams(window.location.search);
  window.userId = urlParams.get('user_id');
  window.securityToken = urlParams.get('token');
  window.gameName = "clicker";
  
  // Initialize Telegram WebApp
  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  } else {
    console.log("Not running in Telegram environment");
  }

  // Create and initialize the game
  const game = new ClickerGame(sessionId);
  game.initializeGame();
});

class ClickerGame {
  constructor(sessionId) {
    this.score = 0;
    this.clickValue = 0.0001;
    this.autoClickers = 0;
    this.incomeMultiplier = 1.0;
    this.upgrades = [];
    this.gameActive = false;
    this.sessionId = sessionId;
    this.saveInterval = null;
    this.lastRewardSend = 0;
    
    this.initializeElements();
  }
  
  initializeElements() {
    this.scoreElement = document.getElementById('score');
    this.clickButton = document.getElementById('click-button');
    this.perClickElement = document.getElementById('per-click');
    this.cpsElement = document.getElementById('cps');
    this.upgradesElement = document.getElementById('upgrades');
    this.autoCollectButton = document.getElementById('auto-collect');
    this.claimButton = document.getElementById('claim-button');
    
    if (this.clickButton) {
      this.clickButton.addEventListener('click', () => this.handleClick());
    }
    
    if (this.autoCollectButton) {
      this.autoCollectButton.addEventListener('click', () => this.collectAuto());
    }
    
    if (this.claimButton) {
      this.claimButton.addEventListener('click', () => this.claimRewards());
    }
  }
  
  async initializeGame() {
    try {
      const response = await this.safeFetch('/api/game/clicker/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({ user_id: window.userId })
      });
      
      if (response.success) {
        this.score = response.user_balance || 0;
        this.clickValue = response.click_value || 0.0001;
        this.autoClickers = response.auto_clickers || 0;
        this.incomeMultiplier = response.income_multiplier || 1.0;
        this.upgrades = response.owned_upgrades || [];
        this.gameActive = true;
        
        this.updateUI();
        this.loadUpgrades(response.game_config?.upgrades || []);
        this.startAutoCollector();
        
        // Start periodic saving
        this.startPeriodicSaving();
        
        // Setup beforeunload event
        window.addEventListener('beforeunload', () => this.saveGame());
      } else {
        this.showError(response.error || 'Failed to initialize game');
      }
    } catch (error) {
      this.showError('Game initialization failed');
    }

    let resetCount = 0;

    function initGame() {
        fetch(`/api/reset-status?game=clicker`)
            .then(res => res.json())
            .then(data => {
                resetCount = data.resets_used;
                updateResetCounter(resetCount);
            });
    }

    function updateResetCounter(count) {
        document.getElementById('reset-counter').textContent = 
            `Resets: ${count}/${MAX_RESETS}`;
    }

    document.getElementById('game-shop-btn').addEventListener('click', () => {
      if (window.parent && window.parent.Miniapp) {
        window.parent.postMessage({type: 'open_shop'}, '*');
      } else {
        window.location.href = '/shop.html';
      }
    });

    // Listen for shop updates
    window.addEventListener('message', (event) => {
      if (event.data.type === 'purchased_item') {
        if (event.data.item_id === 'extra_click_rates') {
          // Add extra time to trivia questions
          timePerQuestion += 10;
          alert('Extra time added! +10 seconds per question');
        }
      }
    });

  }
  
  startPeriodicSaving() {
    // Set up interval for periodic saving
    this.saveInterval = setInterval(() => {
      this.saveGame();
    }, 120000); // 2 minutes
    
    // Initial save
    this.saveGame();
  }
  
  async saveGame() {
    if (!this.gameActive) return;
    
    try {
      const response = await this.safeFetch('/miniapp/game/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || '',
          'X-User-ID': window.userId
        },
        body: JSON.stringify({
          game_id: 'clicker',
          score: this.score,
          session_id: this.sessionId
        })
      });
      
      if (response.success) {
        // Update balance display
        this.score = response.new_balance;
        this.updateUI();
        
        // Show floating reward
        this.showFloatingReward(response.reward);
      }
    } catch (error) {
      console.error('Save game error:', error);
    }
    
    this.lastRewardSend = Date.now();
  }
  
  showFloatingReward(reward) {
    if (!reward || reward <= 0) return;
    
    const floater = document.createElement('div');
    floater.className = 'reward-floater';
    floater.textContent = `+${reward.toFixed(6)} TON`;
    document.body.appendChild(floater);
    
    setTimeout(() => {
      floater.style.opacity = '0';
      setTimeout(() => {
        if (floater.parentNode) {
          document.body.removeChild(floater);
        }
      }, 1000);
    }, 2000);
  }
  
  async safeFetch(url, options) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Fetch error:', error);
      this.showError('Network error. Please check your connection.');
      return { success: false, error: error.message };
    }
  }
  
  async handleClick() {
    if (!this.gameActive) return;
    
    try {
      const response = await fetch('/api/game/clicker/action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({
          user_id: window.userId,
          action: 'click',
          data: {}
        })
      });
      
      const result = await response.json();
      
      if (result.success && result.score !== undefined) {
        this.score = result.score;
        this.updateUI();
        this.showClickEffect();
      }
    } catch (error) {
      console.error('Click error:', error);
    }
  }
  
  async collectAuto() {
    if (!this.gameActive) return;
    
    try {
      const response = await fetch('/api/game/clicker/action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({
          user_id: window.userId,
          action: 'collect_auto',
          data: {}
        })
      });
      
      const result = await response.json();
      
      if (result.success && result.score !== undefined) {
        this.score = result.score;
        this.updateUI();
        
        if (result.auto_earnings > 0) {
          this.showAutoEarnings(result.auto_earnings);
        }
      }
    } catch (error) {
      console.error('Auto collect error:', error);
    }
  }
  
  async buyUpgrade(upgradeId) {
    if (!this.gameActive) return;
    
    try {
      const response = await fetch('/api/game/clicker/action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({
          user_id: window.userId,
          action: 'buy_upgrade',
          data: { upgrade_id: upgradeId }
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        this.score = result.score;
        this.clickValue = result.click_value || this.clickValue;
        this.autoClickers = result.auto_clickers || this.autoClickers;
        this.incomeMultiplier = result.income_multiplier || this.incomeMultiplier;
        this.upgrades = result.owned_upgrades || this.upgrades;
        
        this.updateUI();
        this.updateUpgradeButtons();
      } else {
        this.showError(result.error || 'Failed to buy upgrade');
      }
    } catch (error) {
      console.error('Upgrade error:', error);
    }
  }
  
  loadUpgrades(upgradesList) {
    if (!this.upgradesElement) return;
    
    this.upgradesElement.innerHTML = '';
    
    upgradesList.forEach(upgrade => {
      const upgradeDiv = document.createElement('div');
      upgradeDiv.className = 'upgrade-item';
      upgradeDiv.innerHTML = `
        <div class="upgrade-info">
          <h3>${upgrade.name}</h3>
          <p>${upgrade.description}</p>
          <div class="upgrade-cost">${upgrade.cost} TON</div>
        </div>
        <button class="upgrade-buy" data-upgrade="${upgrade.id}">
          BUY
        </button>
      `;
      
      const buyButton = upgradeDiv.querySelector('.upgrade-buy');
      buyButton.addEventListener('click', () => this.buyUpgrade(upgrade.id));
      
      this.upgradesElement.appendChild(upgradeDiv);
    });
    
    this.updateUpgradeButtons();
  }
  
  updateUpgradeButtons() {
    const buttons = document.querySelectorAll('.upgrade-buy');
    buttons.forEach(button => {
      const upgradeId = button.dataset.upgrade;
      const upgradeDiv = button.closest('.upgrade-item');
      const costElement = upgradeDiv.querySelector('.upgrade-cost');
      const cost = parseFloat(costElement.textContent);
      
      if (this.upgrades.includes(upgradeId)) {
        button.textContent = 'OWNED';
        button.disabled = true;
        button.style.backgroundColor = '#4CAF50';
      } else if (this.score < cost) {
        button.disabled = true;
        button.style.backgroundColor = '#666';
      } else {
        button.disabled = false;
        button.style.backgroundColor = '#2196F3';
      }
    });
  }
  
  updateUI() {
    if (this.scoreElement) {
      this.scoreElement.textContent = this.score.toFixed(6);
    }
    
    if (this.perClickElement) {
      this.perClickElement.textContent = (this.clickValue * this.incomeMultiplier).toFixed(6);
    }
    
    if (this.cpsElement) {
      this.cpsElement.textContent = (this.autoClickers * this.incomeMultiplier).toFixed(2);
    }
    
    this.updateUpgradeButtons();
  }
  
  showClickEffect() {
    if (!this.clickButton) return;
    
    this.clickButton.style.transform = 'scale(0.95)';
    setTimeout(() => {
      this.clickButton.style.transform = 'scale(1)';
    }, 100);
    
    const floatingText = document.createElement('div');
    floatingText.textContent = `+${(this.clickValue * this.incomeMultiplier).toFixed(6)}`;
    floatingText.style.cssText = `
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: #4CAF50;
      font-weight: bold;
      font-size: 20px;
      pointer-events: none;
      z-index: 1000;
      animation: float-up 1s ease-out forwards;
    `;
    
    document.body.appendChild(floatingText);
    setTimeout(() => floatingText.remove(), 1000);
  }
  
  showAutoEarnings(earnings) {
    const notification = document.createElement('div');
    notification.textContent = `Auto collected: ${earnings.toFixed(6)} TON`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 10px 20px;
      border-radius: 5px;
      z-index: 1000;
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
  }
  
  showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    const container = document.querySelector('.clicker-container');
    container.insertBefore(errorDiv, container.firstChild);
    
    setTimeout(() => errorDiv.remove(), 5000);
  }
  
  startAutoCollector() {
    setInterval(() => {
      if (this.autoClickers > 0 && this.gameActive) {
        this.collectAuto();
      }
    }, 5000);
  }
  
  async claimRewards() {
    // Clear periodic saving interval
    clearInterval(this.saveInterval);
    
    try {
      const response = await fetch('/api/game/clicker/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({
          user_id: window.userId,
          score: this.score
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        alert(`Rewards claimed! You earned ${result.reward?.toFixed(6) || '0'} TON`);
        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.close();
        }
      } else {
        this.showError(result.error || 'Failed to claim rewards');
      }
    } catch (error) {
      console.error('Claim error:', error);
      this.showError('Failed to claim rewards');
    }
  }
}

function resetGame(gameId) {
    fetch('/api/game/reset', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-User-ID': window.userId,
            'X-Telegram-Hash': window.initDataHash
        },
        body: JSON.stringify({
            game_id: gameId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Telegram.WebApp.showAlert(`Game reset! ${data.resets_left} resets left today`);
            // Reload or reset the game
        } else {
            Telegram.WebApp.showAlert(data.error || 'Reset failed');
        }
    });
}

function handleReset() {
    fetch('/api/game/reset', {
        method: 'POST',
        body: JSON.stringify({game: 'clicker'})
    }).then(checkResetAvailability);
}

// Handle reset button
document.getElementById('reset-btn').addEventListener('click', () => {
    if (resetCount >= MAX_RESETS) {
        alert("Daily reset limit reached");
        return;
    }
    handleReset('clicker');
});