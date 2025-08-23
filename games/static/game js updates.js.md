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



2. /templates/shop.html - Add gifts section:

<!-- Add this to the shop items section -->
<div class="shop-item">
    <div class="item-header">
        <h3>🎁 Send Gift to Friend</h3>
    </div>
    <div class="item-icon">🎁</div>
    <div class="item-body">
        <p>Send a special gift to your friends!</p>
        <div class="item-price">Starting from: 100 Stars</div>
        <button class="btn-buy" onclick="openGiftSelection()">Choose Gift</button>
    </div>
</div>

<!-- Add gift selection modal -->
<div class="modal" id="gift-modal">
    <div class="modal-content">
        <span class="close" onclick="closeGiftModal()">&times;</span>
        <h2>🎁 Select a Gift</h2>
        <div id="gift-selection">
            <!-- Gift options will be loaded here -->
        </div>
    </div>
</div>

<script>
async function openGiftSelection() {
    const response = await fetch('/api/gifts/available');
    const gifts = await response.json();
    
    const giftSelection = document.getElementById('gift-selection');
    giftSelection.innerHTML = '';
    
    gifts.forEach(gift => {
        const giftElement = document.createElement('div');
        giftElement.className = 'gift-option';
        giftElement.innerHTML = `
            <img src="${gift.image_url}" alt="${gift.name}">
            <h4>${gift.name}</h4>
            <p>${gift.stars} Stars</p>
            <button onclick="selectGift(${gift.id})">Select</button>
        `;
        giftSelection.appendChild(giftElement);
    });
    
    document.getElementById('gift-modal').style.display = 'block';
}

async function selectGift(giftId) {
    // Prompt for recipient and send gift
    const recipient = prompt("Enter recipient's username or ID:");
    if (recipient) {
        const response = await fetch('/api/gifts/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({gift_id: giftId, recipient: recipient})
        });
        
        if (response.ok) {
            alert('Gift sent successfully!');
            closeGiftModal();
        } else {
            alert('Error sending gift');
        }
    }
}
</script>