document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram.WebApp;
    const userId = tg.initDataUnsafe.user?.id || 'guest';
    
    // DOM elements
    const clickButton = document.getElementById('click-button');
    const scoreEl = document.getElementById('score');
    const cpsEl = document.getElementById('cps');
    const upgradesEl = document.getElementById('upgrades');
    const autoCollectButton = document.getElementById('auto-collect');
    
    // Game state
    let clickValue = 0.0001;
    let autoClickers = 0;
    let incomeMultiplier = 1.0;
    let lastAutoCollect = Date.now();
    let upgrades = [];
    
    // Initialize game
    startGame();
    
    function startGame() {
        fetch(`/games/clicker/start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === "started") {
                loadGameData();
            }
        });
    }
    
    function loadGameData() {
        fetch(`/games/clicker`)
        .then(res => res.json())
        .then(data => {
            clickValue = data.game_data.base_value;
            renderUpgrades(data.game_data.upgrades);
        });
    }
    
    function renderUpgrades(upgradeList) {
        upgradesEl.innerHTML = '';
        upgradeList.forEach(upgrade => {
            const upgradeEl = document.createElement('div');
            upgradeEl.className = 'upgrade';
            upgradeEl.innerHTML = `
                <h3>${upgrade.name}</h3>
                <p>${upgrade.description}</p>
                <div class="upgrade-cost">${upgrade.cost.toFixed(6)} TON</div>
                <button class="buy-button" data-id="${upgrade.id}">BUY</button>
            `;
            upgradesEl.appendChild(upgradeEl);
        });
        
        // Add event listeners to buy buttons
        document.querySelectorAll('.buy-button').forEach(button => {
            button.addEventListener('click', () => {
                const upgradeId = button.dataset.id;
                buyUpgrade(upgradeId);
            });
        });
    }
    
    clickButton.addEventListener('click', () => {
        fetch(`/games/clicker/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                action: "click"
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.score !== undefined) {
                scoreEl.textContent = data.score.toFixed(6);
                
                // Animate button
                clickButton.classList.add('clicked');
                setTimeout(() => {
                    clickButton.classList.remove('clicked');
                }, 100);
            } else if (data.error) {
                alert(data.error);
            }
        });
    });
    
    autoCollectButton.addEventListener('click', () => {
        fetch(`/games/clicker/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                action: "collect_auto"
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.score !== undefined) {
                scoreEl.textContent = data.score.toFixed(6);
                lastAutoCollect = Date.now();
                autoCollectButton.disabled = true;
                setTimeout(() => {
                    autoCollectButton.disabled = false;
                }, 10000);  // 10 seconds cooldown
            }
        });
    });
    
    function buyUpgrade(upgradeId) {
        fetch(`/games/clicker/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                action: "buy_upgrade",
                data: {upgrade_id: upgradeId}
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.score !== undefined) {
                scoreEl.textContent = data.score.toFixed(6);
                
                if (data.click_value) clickValue = data.click_value;
                if (data.auto_clickers) autoClickers = data.auto_clickers;
                if (data.income_multiplier) incomeMultiplier = data.income_multiplier;
                
                // Update CPS display
                const cps = autoClickers * incomeMultiplier;
                cpsEl.textContent = cps.toFixed(2);
                
                // Visual feedback
                const button = document.querySelector(`.buy-button[data-id="${upgradeId}"]`);
                button.textContent = "OWNED";
                button.disabled = true;
                button.classList.add('owned');
            } else if (data.error) {
                alert(data.error);
            }
        });
    }
    
    // Auto-collect indicator animation
    setInterval(() => {
        const elapsed = (Date.now() - lastAutoCollect) / 1000;
        const earnings = autoClickers * elapsed * incomeMultiplier;
        
        if (earnings > 0) {
            autoCollectButton.textContent = `COLLECT ${earnings.toFixed(2)} TON`;
            autoCollectButton.classList.add('pulse');
        } else {
            autoCollectButton.textContent = "AUTO COLLECT";
            autoCollectButton.classList.remove('pulse');
        }
    }, 1000);
    
    // Claim button
    document.getElementById('claim-button').addEventListener('click', () => {
        fetch(`/games/clicker/end`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        })
        .then(res => res.json())
        .then(data => {
            tg.sendData(JSON.stringify({
                type: "claim_rewards",
                game: "clicker",
                amount: data.score,
                user_id: userId
            }));
        });
    });
});