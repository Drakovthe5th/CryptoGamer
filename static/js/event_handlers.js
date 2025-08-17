document.addEventListener('DOMContentLoaded', function() {
  // Handle all action buttons
  document.querySelectorAll('[data-action]').forEach(button => {
    button.addEventListener('click', async function() {
      const action = this.dataset.action;
      const endpoint = this.dataset.endpoint;
      const amount = this.dataset.amount || '';
      
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
          },
          body: JSON.stringify({ amount })
        });
        
        const data = await response.json();
        
        if (data.success) {
          if (data.new_balance) {
            updateBalanceDisplay(data.new_balance);
          }
          showToast(`${action.replace('_', ' ')} successful!`);
        } else {
          showToast(`Error: ${data.error || 'Action failed'}`, 'error');
        }
      } catch (error) {
        showToast('Network error. Please try again.', 'error');
        console.error('Action error:', error);
      }
    });
  });

  // Anti-cheat initialization
    Telegram.WebApp.onEvent('viewportChanged', (event) => {
        if (event.isStateStable) {
            // Detect if user switched away from game
            const gameContainer = document.getElementById('game-iframe');
            if (gameContainer.style.display === 'block') {
                Miniapp.recordSuspiciousActivity('viewport_changed_during_gameplay');
            }
        }
    });
  
  // Shop item purchase handlers
  document.querySelectorAll('.shop-item').forEach(item => {
    item.addEventListener('click', function() {
      const itemId = this.dataset.item;
      purchaseItem(itemId);
    });
  });
  
  // Game launch handlers
  document.querySelectorAll('.game-card').forEach(card => {
    card.addEventListener('click', function() {
      const gameId = this.dataset.gameId;
      launchGame(gameId);
    });
  });
  
  // Close game button
  document.getElementById('close-game-btn').addEventListener('click', function() {
    document.getElementById('game-iframe-page').style.display = 'none';
  });
  
  // Update balance display
  function updateBalanceDisplay(balance) {
    const balanceElements = document.querySelectorAll('.balance-display');
    balanceElements.forEach(el => {
      el.textContent = balance.toFixed(6) + ' TON';
    });
  }
  
  // Toast notification
  function showToast(message, type = 'success') {
    // Implement toast notifications here
    alert(`${type.toUpperCase()}: ${message}`);
  }
  
  // Purchase item function
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
        showToast(`Purchased ${data.itemName}!`);
        // Update GC balance display
        document.querySelectorAll('#gc-balance').forEach(el => {
          el.textContent = `${data.newGCBalance} GC`;
        });
      } else {
        showToast(`Purchase failed: ${data.error}`, 'error');
      }
    })
    .catch(error => {
      hideSpinner();
      showToast('Purchase failed. Please try again.', 'error');
      console.error('Purchase error:', error);
    });
  }
  
  // Launch game function
  function launchGame(gameId) {
    showSpinner();
    fetch(`/api/games/launch/${gameId}`, {
      headers: {
        'X-Telegram-Hash': window.Telegram.WebApp.initData
      }
    })

        // Generate anti-cheat challenge
    fetch(`/api/anti-cheat/challenge?game=${gameId}`)
        .then(response => response.json())
        .then(data => {
            if (data.challenge) {
                localStorage.setItem('anti-cheat-challenge', data.challenge);
            }
    });

    .then(response => response.json())
    .then(data => {
      hideSpinner();
      if (data.url) {
        document.getElementById('game-iframe').src = data.url;
        document.getElementById('game-iframe-page').style.display = 'block';
      }
    })
    .catch(error => {
      hideSpinner();
      showToast('Failed to launch game.', 'error');
      console.error('Game launch error:', error);
    });
  }

  function handleGameCompletion(score) {
    const challenge = localStorage.getItem('anti-cheat-challenge');
    fetch(`/api/anti-cheat/verify`, {
        method: 'POST',
        body: JSON.stringify({
            challenge: challenge,
            response: calculateAntiCheatResponse(challenge)
            })
        }).then(/* verify before accepting score */);
    }

    function calculateAntiCheatResponse(challenge) {
        // Client-side proof-of-work calculation
        return sha256(challenge + 'secret_salt');
    }
});