window.gameInputHistory = [];
window.userId = Telegram.WebApp.initDataUnsafe.user.id;

document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram.WebApp;
    const userId = tg.initDataUnsafe.user?.id || 'guest';
    
    // DOM elements
    const wheel = document.getElementById('wheel');
    const pointer = document.getElementById('pointer');
    const spinButton = document.getElementById('spin-button');
    const balanceEl = document.getElementById('balance');
    const spinsEl = document.getElementById('spins');
    const resultEl = document.getElementById('result');
    const resultText = document.getElementById('result-text');
    const resultAmount = document.getElementById('result-amount');
    
    // Game state
    let isSpinning = false;
    let wheelSections = [];
    let playerBalance = 0;
    let spinCount = 0;
    
    // Initialize game
    initGame();
    
    async function initGame() {
        const response = await fetch(`/games/spin/start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });
        
        const data = await response.json();
        if (data.status === "ready") {
            // Get initial game data
            const initResponse = await fetch(`/games/spin`);
            const initData = await initResponse.json();
            
            wheelSections = initData.game_data.wheel;
            renderWheel();
            updateBalance(0);
        }
    }
    
    function renderWheel() {
        wheel.innerHTML = '';
        const centerX = wheel.offsetWidth / 2;
        const centerY = wheel.offsetHeight / 2;
        const radius = Math.min(centerX, centerY) - 10;
        let startAngle = 0;
        
        wheelSections.forEach((section, index) => {
            const sliceAngle = 2 * Math.PI / wheelSections.length;
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
            
            wheel.appendChild(path);
            wheel.appendChild(text);
            
            startAngle = endAngle;
        });
    }
    
    spinButton.addEventListener('click', async () => {
        if (isSpinning) return;
        
        isSpinning = true;
        spinButton.disabled = true;
        
        // Perform spin action
        const response = await fetch(`/games/spin/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                action: "spin"
            })
        });
        
        const data = await response.json();
        if (data.error) {
            alert(data.error);
            isSpinning = false;
            spinButton.disabled = false;
            return;
        }
        
        // Animate spin
        const result = data.result;
        const resultIndex = wheelSections.findIndex(s => s.id === result.id);
        const sliceAngle = 360 / wheelSections.length;
        const targetRotation = 360 * 5 + (360 - (resultIndex * sliceAngle) - (sliceAngle / 2));
        
        wheel.style.transition = 'transform 4s cubic-bezier(0.34, 1.56, 0.64, 1)';
        wheel.style.transform = `rotate(${targetRotation}deg)`;
        
        // Show result after animation
        setTimeout(() => {
            updateBalance(data.score);
            spinsEl.textContent = data.spins;
            
            resultText.textContent = result.id.toUpperCase();
            resultAmount.textContent = `${result.value} TON`;
            resultEl.style.display = 'block';
            
            setTimeout(() => {
                resultEl.style.display = 'none';
                isSpinning = false;
                spinButton.disabled = false;
            }, 3000);
        }, 4200);
    });
    
    function updateBalance(balance) {
        playerBalance = balance;
        balanceEl.textContent = playerBalance.toFixed(6);
    }
    
    document.getElementById('cashout-button').addEventListener('click', async () => {
        const response = await fetch(`/games/spin/end`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        });
        
        const data = await response.json();
        if (data.error) {
            alert(data.error);
            return;
        }
        
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
                    user_id: userId
                }));
            }
        });
    });
});

// Example implementation for Spin game
class SpinGame {
    constructor() {
        this.score = 0;
        this.sessionId = this.generateSessionId();
        this.startTime = Date.now();
    }
    
    generateSessionId() {
        return 'spin-' + Math.random().toString(36).substring(2, 15) + 
               Date.now().toString(36);
    }
    
    startGame() {
        // Game initialization logic
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.getElementById('spin-button').addEventListener('click', () => {
            this.spinWheel();
        });
    }
    
    spinWheel() {
        // Spin animation logic
        const result = Math.floor(Math.random() * 10);
        
        setTimeout(() => {
            this.handleSpinResult(result);
        }, 3000);

            const session_data = {
            startTime: gameStartTime,
            endTime: Date.now(),
            spins: spinCount,
            wins: winCount,
            coins: currentCoins,
            userActions: window.gameInputHistory
        };
        
        window.reportGameCompletion(currentCoins, session_data);
    }
    
    handleSpinResult(result) {
        this.score = result;
        const winAmount = result * 10; // Example
        
        // Show result to user
        this.showResult(winAmount);
        
        // Report game completion to backend
        this.reportCompletion();
    }
    
    showResult(winAmount) {
        // UI update to show winnings
        document.getElementById('result').innerText = 
            `You won ${winAmount} points!`;
    }
    
    getSessionData() {
        return {
            session_id: this.sessionId,
            start_time: this.startTime,
            end_time: Date.now(),
            actions: this.collectActions(),  // Would collect user actions during gameplay
            device_info: this.getDeviceInfo()
        };
    }
    
    collectActions() {
        // Return array of important game actions
        return [
            { action: 'spin', timestamp: Date.now() - 3500 },
            { action: 'result', timestamp: Date.now(), value: this.score }
        ];
    }
    
    getDeviceInfo() {
        return {
            user_agent: navigator.userAgent,
            screen: `${screen.width}x${screen.height}`,
            platform: navigator.platform
        };
    }
    
    reportCompletion() {
        // Get Telegram user ID if available
        let userId = null;
        if (window.Telegram && window.Telegram.WebApp) {
            userId = window.Telegram.WebApp.initDataUnsafe.user?.id;
        }
        
        if (!userId) {
            console.error("User ID not available");
            return;
        }
        
        const sessionData = this.getSessionData();
        
        fetch('/api/game/complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                game_id: 'spin',
                score: this.score,
                session_data: sessionData
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Earned ${data.reward} TON!`);
                // Update UI with reward
                document.getElementById('ton-reward').innerText = 
                    `+${data.reward.toFixed(4)} TON`;
            } else {
                console.error('Game completion failed:', data.error);
            }
        })
        .catch(error => {
            console.error('Error reporting game completion:', error);
        });
    }
}

// Example for T-Rex Runner
window.gameOver = function(distance) {
    reportGameCompletion({
        game_id: 'trex-runner',
        score: distance,
        session_data: {
            startTime: performance.now() - gameDuration,
            endTime: performance.now(),
            jump_count: playerJumpCount
        }
    });
};

window.reportGameCompletion = function(score, session_data) {
    fetch('/api/game/complete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Security-Token': window.securityToken
        },
        body: JSON.stringify({
            user_id: window.userId,
            game_id: 'spin',
            score: score,
            session_data: session_data
        })
    });
};

document.getElementById('spin-button').addEventListener('click', () => {
    window.gameInputHistory.push({
        type: 'spin',
        timestamp: Date.now(),
        coins: currentCoins
    });
});

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    const game = new SpinGame();
    game.startGame();
});