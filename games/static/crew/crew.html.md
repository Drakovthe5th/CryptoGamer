5. Frontend Updates (static/crew/index.html)

<!-- Add to the game-info section -->
<div class="info-box">
    <div class="info-label">CREW CREDITS</div>
    <div class="info-value" id="crew-credits">0</div>
</div>

<!-- Add to the action-panel -->
<button class="action-btn" id="btn-buy-credits">Buy Crew Credits</button>

<!-- Add modals for credit purchase -->
<div class="modal" id="credits-modal">
    <div class="modal-content">
        <div class="modal-header">
            <h2 class="modal-title">Buy Crew Credits</h2>
            <button class="close-modal">&times;</button>
        </div>
        <div class="modal-body">
            <p>Crew Credits are used exclusively for Crypto Crew: Sabotage.</p>
            <div class="credit-options">
                <div class="credit-option" data-stars="100">
                    <div class="stars-amount">100 Stars</div>
                    <div class="credits-amount">10,000 Credits</div>
                    <button class="btn-primary">Purchase</button>
                </div>
                <div class="credit-option" data-stars="500">
                    <div class="stars-amount">500 Stars</div>
                    <div class="credits-amount">50,000 Credits</div>
                    <button class="btn-primary">Purchase</button>
                </div>
                <div class="credit-option" data-stars="1000">
                    <div class="stars-amount">1000 Stars</div>
                    <div class="credits-amount">100,000 Credits</div>
                    <button class="btn-primary">Purchase</button>
                </div>
            </div>
        </div>
    </div>
</div>


6. Frontend JavaScript (static/crew/js/game.js)

// Add to game initialization
async function loadCreditsBalance() {
    try {
        const response = await fetch('/api/crew/credits/balance', {
            headers: {
                'X-Telegram-InitData': window.Telegram.WebApp.initData
            }
        });
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('crew-credits').textContent = data.crew_credits.toLocaleString();
            
            // Enable/disable join button based on credits
            const joinButton = document.getElementById('btn-join-game');
            if (joinButton) {
                joinButton.disabled = data.crew_credits < 100;
            }
        }
    } catch (error) {
        console.error('Error loading credits balance:', error);
    }
}

// Add event listener for buy credits button
document.getElementById('btn-buy-credits').addEventListener('click', () => {
    document.getElementById('credits-modal').style.display = 'flex';
});

// Add event listeners for credit options
document.querySelectorAll('.credit-option').forEach(option => {
    option.querySelector('button').addEventListener('click', async () => {
        const starsAmount = option.dataset.stars;
        
        try {
            const response = await fetch('/api/crew/credits/purchase', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-InitData': window.Telegram.WebApp.initData
                },
                body: JSON.stringify({ stars_amount: parseInt(starsAmount) })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update credits display
                document.getElementById('crew-credits').textContent = data.new_credits_balance.toLocaleString();
                
                // Close modal
                document.getElementById('credits-modal').style.display = 'none';
                
                // Show success message
                showNotification('Purchase Successful', `You bought ${data.credits_amount.toLocaleString()} Crew Credits!`);
            } else {
                showNotification('Purchase Failed', data.error || 'Unknown error occurred');
            }
        } catch (error) {
            console.error('Error purchasing credits:', error);
            showNotification('Purchase Failed', 'Network error occurred');
        }
    });
});

// Call this when the game loads
window.addEventListener('load', () => {
    loadCreditsBalance();
    // ... other initialization code
});


7. CSS Styling (static/crew/css/style.css)

/* Add to existing CSS */
.credit-options {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
    margin: 20px 0;
}

.credit-option {
    background-color: rgba(40, 40, 70, 0.5);
    border-radius: 10px;
    padding: 15px;
    text-align: center;
    border: 2px solid transparent;
    transition: all 0.3s ease;
    cursor: pointer;
}

.credit-option:hover {
    border-color: var(--accent);
    box-shadow: var(--accent-glow);
}

.stars-amount {
    font-size: 18px;
    font-weight: bold;
    color: var(--accent);
    margin-bottom: 5px;
}

.credits-amount {
    font-size: 16px;
    margin-bottom: 10px;
}

/* Update existing styles for dual currency display */
.info-box {
    /* Keep existing styles */
}

.info-value {
    /* Keep existing styles */
}



7. Update Game Files (clicker.js, spin.js, trivia.js)

Add web events integration to each game:

// Add to the initialization section of each game
document.addEventListener('DOMContentLoaded', () => {
  // ... existing code ...
  
  // Initialize Telegram Web Events
  if (window.TelegramWebEvents) {
    // Setup game-specific buttons and events
    window.TelegramWebEvents.setupMainButton(true, true, 'Play Now', '#3390ec', '#ffffff', false, true);
    
    // Share functionality
    window.shareScore = function(score) {
      window.TelegramWebEvents.shareScore(score, window.gameName);
    };
    
    window.shareGame = function() {
      window.TelegramWebEvents.shareGame(window.gameName);
    };
  }
  
  // ... rest of existing code ...
});

// Add to the claimRewards function in each game
function claimRewards() {
  if (window.TelegramWebEvents) {
    window.TelegramWebEvents.openInvoice('game_rewards_' + window.gameName);
  } else {
    // Fallback for non-Telegram environment
    alert(`Rewards claimed! You earned ${totalReward.toFixed(6)} TON`);
  }
}