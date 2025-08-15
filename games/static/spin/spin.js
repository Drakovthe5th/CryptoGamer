// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
  // Get session ID from URL
  const sessionId = new URLSearchParams(window.location.search).get('session_id');
  
  // Get user data
  const urlParams = new URLSearchParams(window.location.search);
  window.userId = urlParams.get('user_id');
  window.securityToken = urlParams.get('token');
  window.gameName = "spin";
  
  // Initialize Telegram WebApp
  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  } else {
    console.log("Not running in Telegram environment");
  }

  // Create and initialize the game
  const game = new SpinGame(sessionId);
  game.initializeGame();
});

class SpinGame {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.saveInterval = null;
    this.lastRewardSend = 0;
    this.totalWinnings = 0;
    
    // Initialize elements
    this.wheel = document.getElementById('wheel');
    this.spinButton = document.getElementById('spin-button');
    this.balanceEl = document.getElementById('balance');
    this.spinsEl = document.getElementById('spins');
    this.totalWinningsEl = document.getElementById('total-winnings');
    this.resultEl = document.getElementById('result');
    this.resultText = document.getElementById('result-text');
    this.resultAmount = document.getElementById('result-amount');
    this.cashoutButton = document.getElementById('cashout-button');
    
    // Game state
    this.isSpinning = false;
    this.wheelSections = [];
    this.playerBalance = 0;
    this.spinCount = 0;
  }
  
  async initializeGame() {
    try {
      const response = await this.safeFetch(`/api/game/${window.gameName}/init`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({user_id: window.userId})
      });
      
      if (response.success) {
        this.playerBalance = response.user_balance || 0;
        this.wheelSections = response.game_config?.wheel || [];
        this.updateBalance();
        this.renderWheel();
        
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
    try {
      const response = await this.safeFetch('/miniapp/game/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || '',
          'X-User-ID': window.userId
        },
        body: JSON.stringify({
          game_id: 'spin',
          score: this.totalWinnings,
          session_id: this.sessionId
        })
      });
      
      if (response.success) {
        // Update balance display
        this.playerBalance = response.new_balance;
        this.updateBalance();
        
        // Show floating reward if any
        if (response.reward > 0) {
          this.showFloatingReward(response.reward);
        }
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
  
  renderWheel() {
    this.wheel.innerHTML = '';
    const centerX = 150;
    const centerY = 150;
    const radius = 140;
    let startAngle = 0;
    const sliceAngle = 2 * Math.PI / this.wheelSections.length;
    
    this.wheelSections.forEach((section, index) => {
      const endAngle = startAngle + sliceAngle;
      
      // Create slice path
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const startX = centerX + radius * Math.cos(startAngle);
      const startY = centerY + radius * Math.sin(startAngle);
      const endX = centerX + radius * Math.cos(endAngle);
      const endY = centerY + radius * Math.sin(endAngle);
      
      const largeArc = sliceAngle > Math.PI ? 1 : 0;
      
      path.setAttribute('d', `
        M ${centerX},${centerY}
        L ${startX},${startY}
        A ${radius} ${radius} 0 ${largeArc} 1 ${endX},${endY}
        Z
      `);
      
      path.setAttribute('fill', section.color);
      path.setAttribute('data-index', index);
      path.classList.add('wheel-slice');
      
      // Add text
      const textAngle = startAngle + sliceAngle / 2;
      const textX = centerX + (radius * 0.7) * Math.cos(textAngle);
      const textY = centerY + (radius * 0.7) * Math.sin(textAngle);
      
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', textX);
      text.setAttribute('y', textY);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', '#ffffff');
      text.setAttribute('font-size', '14');
      text.setAttribute('transform', `rotate(${textAngle * 180/Math.PI + 90}, ${textX}, ${textY})`);
      text.textContent = section.value;
      
      this.wheel.appendChild(path);
      this.wheel.appendChild(text);
      
      startAngle = endAngle;
    });
  }
  
  async handleSpin() {
    if (this.isSpinning) return;
    
    this.isSpinning = true;
    this.spinButton.disabled = true;
    
    try {
      // Perform spin action
      const response = await fetch(`/api/game/${window.gameName}/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({
          user_id: window.userId,
          action: "spin"
        })
      });
      
      const data = await response.json();
      if (data.error) {
        alert(data.error);
        this.isSpinning = false;
        this.spinButton.disabled = false;
        return;
      }
      
      // Animate spin
      const result = data.result;
      const resultIndex = this.wheelSections.findIndex(s => s.id === result.id);
      const sliceAngle = 360 / this.wheelSections.length;
      const targetRotation = 360 * 5 + (360 - (resultIndex * sliceAngle) - (sliceAngle / 2));
      
      this.wheel.style.transition = 'transform 4s cubic-bezier(0.34, 1.56, 0.64, 1)';
      this.wheel.style.transform = `rotate(${targetRotation}deg)`;
      
      // Show result after animation
      setTimeout(() => {
        this.playerBalance = data.score;
        this.spinCount = data.spins;
        this.totalWinnings += result.value;
        
        this.updateBalance();
        this.spinsEl.textContent = this.spinCount;
        this.totalWinningsEl.textContent = this.totalWinnings.toFixed(6);
        
        this.resultText.textContent = result.id.toUpperCase();
        this.resultAmount.textContent = `${result.value} TON`;
        this.resultEl.style.display = 'block';
        
        // Report spin completion to server
        this.reportSpinCompletion(result.value);
        
        setTimeout(() => {
          this.resultEl.style.display = 'none';
          this.isSpinning = false;
          this.spinButton.disabled = false;
        }, 3000);
      }, 4200);
    } catch (error) {
      console.error('Spin error:', error);
      this.isSpinning = false;
      this.spinButton.disabled = false;
    }
  }
  
  async reportSpinCompletion(value) {
    try {
      const response = await this.safeFetch('/miniapp/game/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || '',
          'X-User-ID': window.userId
        },
        body: JSON.stringify({
          game_id: 'spin',
          score: value,
          session_id: this.sessionId
        })
      });
      
      if (response.success) {
        // Update balance
        this.playerBalance = response.new_balance;
        this.updateBalance();
        
        // Show floating reward
        if (response.reward > 0) {
          this.showFloatingReward(response.reward);
        }
      }
    } catch (error) {
      console.error('Spin completion report error:', error);
    }
  }
  
  updateBalance() {
    this.balanceEl.textContent = this.playerBalance.toFixed(6);
  }
  
  async handleCashout() {
    // Clear periodic saving interval
    clearInterval(this.saveInterval);
    
    try {
      const response = await fetch(`/api/game/${window.gameName}/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Security-Token': window.securityToken || ''
        },
        body: JSON.stringify({user_id: window.userId})
      });
      
      const data = await response.json();
      if (data.error) {
        alert(data.error);
        return;
      }
      
      const tg = window.Telegram?.WebApp;
      if (tg && tg.showPopup) {
        tg.showPopup({
          title: "Cash Out Successful!",
          message: `You've cashed out ${data.total_winnings.toFixed(6)} TON`,
          buttons: [{
            id: 'claim',
            type: 'default',
            text: 'Claim TON'
          }]
        }, (btnId) => {
          if (btnId === 'claim') {
            tg.sendData(JSON.stringify({
              type: "claim_rewards",
              game: "spin",
              amount: data.total_winnings,
              user_id: window.userId
            }));
          }
        });
      } else {
        alert(`Cash Out Successful! You've cashed out ${data.total_winnings.toFixed(6)} TON`);
      }
    } catch (error) {
      console.error('Cashout error:', error);
    }
  }
  
  showError(message) {
    alert(message);
  }
  
  setupEventListeners() {
    if (this.spinButton) {
      this.spinButton.addEventListener('click', () => this.handleSpin());
    }
    
    if (this.cashoutButton) {
      this.cashoutButton.addEventListener('click', () => this.handleCashout());
    }
  }
}

// Initialize the game
const game = new SpinGame();
game.setupEventListeners();