4. Update /templates/miniapp.html
Add the Telegram Web Events script and update UI elements:

<!-- Add this script tag in the head section -->
<script src="/static/js/telegram-web-events.js"></script>

<!-- Update the shop items to include Stars pricing -->
<div class="shop-item">
  <div class="shop-item-info">
    <div class="shop-item-name">2x Earnings Booster</div>
    <div class="shop-item-price">
      <span>2000 GC</span>
      <span class="stars-price">or 200 Stars</span>
    </div>
  </div>
  <button class="shop-item-button" onclick="purchaseItem('global_booster', 2000)">Buy</button>
</div>

<!-- Add haptic feedback to buttons -->
<script>
  // Add haptic feedback to interactive elements
  document.querySelectorAll('button, .game-card, .nav-item').forEach(element => {
    element.addEventListener('click', () => {
      triggerHapticFeedback('selection_change');
    });
  });
</script>


Step 5: Update UI for Attachment Menu

File: templates/miniapp.html - Add attachment menu section:

<!-- Add to the main content -->
<section id="attach-menu-page" class="page">
    <div class="page-header">
        <h2>📎 Attachment Menu</h2>
        <p>Manage your mini-apps and quick access tools</p>
    </div>
    
    <div class="home-section">
        <h3>Installed Mini-Apps</h3>
        <div id="installed-bots-list" class="bot-list">
            <!-- Dynamically populated -->
        </div>
    </div>
    
    <div class="home-section">
        <h3>Available Mini-Apps</h3>
        <div id="available-bots-list" class="bot-list">
            <!-- Dynamically populated -->
        </div>
    </div>
</section>

<!-- Add to navigation -->
<a href="#attach-menu" class="nav-item" data-page="attach-menu">
    <span class="nav-icon">📎</span>
    <span class="nav-label">Mini-Apps</span>
</a>


##Add Sabotage Game

<!-- Add to the games section -->
<div class="game-card" data-game="sabotage">
    <div class="game-icon">🕵️</div>
    <div class="game-info">
        <h3>Crypto Crew: Sabotage</h3>
        <p>Social deduction game - Find the saboteurs!</p>
        <div class="game-stats">
            <span class="stat">👥 4-6 players</span>
            <span class="stat">⏱️ 15 min</span>
            <span class="stat">💰 Up to 8000 GC</span>
        </div>
    </div>
    <button class="play-btn" onclick="launchGame('sabotage')">Play</button>
</div>