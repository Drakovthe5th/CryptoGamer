window.gameInputHistory = [];
window.userId = Telegram.WebApp.initDataUnsafe.user.id;

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

// Clicker Game Implementation
class ClickerGame {
    constructor() {
        this.clicks = 0;
        this.sessionId = this.generateSessionId();
        this.startTime = Date.now();
        this.clickTimes = [];
    }
    
    generateSessionId() {
        return 'clicker-' + Math.random().toString(36).substring(2, 15) + 
               Date.now().toString(36);
    }
    
    startGame() {
        document.getElementById('click-area').addEventListener('click', () => {
            this.handleClick();
        });
        
        document.getElementById('complete-btn').addEventListener('click', () => {
            this.completeGame();
        });
    }
    
    handleClick() {
        this.clicks++;
        this.clickTimes.push(Date.now());
        document.getElementById('click-count').innerText = this.clicks;
        
        // Visual feedback
        const clickArea = document.getElementById('click-area');
        clickArea.classList.add('clicked');
        setTimeout(() => clickArea.classList.remove('clicked'), 100);
    }
    
    completeGame() {
        const sessionData = this.getSessionData();
        
        // Get Telegram user ID if available
        let userId = null;
        if (window.Telegram && window.Telegram.WebApp) {
            userId = window.Telegram.WebApp.initDataUnsafe.user?.id;
        }
        
        if (!userId) {
            alert("User not authenticated. Please play through Telegram.");
            return;
        }
        
        fetch('/api/game/complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                game_id: 'clicker',
                score: this.clicks,
                session_data: sessionData
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Game complete! You earned ${data.reward.toFixed(4)} TON`);
            } else {
                alert(`Error: ${data.error || 'Failed to complete game'}`);
            }
        });
    }
    
    getSessionData() {
        return {
            session_id: this.sessionId,
            start_time: this.startTime,
            end_time: Date.now(),
            total_clicks: this.clicks,
            click_times: this.clickTimes,
            device_info: {
                user_agent: navigator.userAgent,
                screen: `${screen.width}x${screen.height}`,
                platform: navigator.platform
            }
        };
    }
}

// Initialize game
document.addEventListener('DOMContentLoaded', () => {
    const game = new ClickerGame();
    game.startGame();
});

// Track clicks
document.getElementById('clicker-button').addEventListener('click', () => {
    window.gameInputHistory.push({
        type: 'click',
        element: 'main-button',
        timestamp: Date.now()
    });
});

// Track upgrades
document.querySelectorAll('.upgrade-button').forEach(button => {
    button.addEventListener('click', () => {
        window.gameInputHistory.push({
            type: 'click',
            element: 'upgrade-' + button.dataset.id,
            timestamp: Date.now()
        });
    });
});

function reportGameCompletion(score) {
     fetch('/api/game/complete', {
         method: 'POST',
         headers: {
             'Content-Type': 'application/json'
         },
         body: JSON.stringify({
             game_id: 'clicker', // or other game ID
             score: score
         })
     })
     .then(response => response.json())
     .then(data => {
         if (data.success) {
             console.log('Reward earned:', data.reward);
         }
     });
}

// Example for Spin Game
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('spin-button')) {
        window.gameInputHistory.push({
            type: 'click',
            element: 'spin-button',
            timestamp: performance.now()
        });
    }
});

window.reportGameCompletion = function(score, session_data) {
    fetch('/api/game/complete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Security-Token': window.securityToken
        },
        body: JSON.stringify({
            user_id: window.userId,
            game_id: 'clicker',
            score: score,
            session_data: session_data
        })
    });
};

function onGameExit() {
    const session_data = {
        startTime: gameStartTime,
        endTime: Date.now(),
        clicks: totalClicks,
        auto_clicks: totalAutoClicks,
        upgrades: purchasedUpgrades,
        userActions: window.gameInputHistory
    };
    
    window.reportGameCompletion(playerScore, session_data);
}