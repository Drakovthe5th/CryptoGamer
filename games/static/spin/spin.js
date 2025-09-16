// spin.js - Complete Rewrite with Advanced Features
class SpinGame {
    constructor() {
        this.isSpinning = false;
        this.playerBalance = 0;
        this.spinCount = 0;
        this.totalWinnings = 0;
        this.wheelSections = [];
        this.sessionId = null;
        this.boosters = {
            multiplier: 1,
            extraSpins: 0,
            freeSpins: 0
        };
        
        this.initializeGame();
    }

    async initializeGame() {
        // Initialize Telegram WebApp
        this.initTelegramWebApp();
        
        // Load game configuration
        await this.loadGameConfig();
        
        // Initialize UI elements
        this.initializeElements();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Check for active boosters
        await this.checkActiveBoosters();
        
        // Check for daily bonus
        await this.checkDailyBonus();
        
        // Update UI
        this.updateUI();
    }

    initTelegramWebApp() {
        // Initialize Telegram WebApp if available
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
            
            // Set up main button
            window.Telegram.WebApp.MainButton.setText('SPIN TO WIN');
            window.Telegram.WebApp.MainButton.show();
            window.Telegram.WebApp.MainButton.onClick(this.handleSpin.bind(this));
            
            // Get user data from Telegram
            const user = window.Telegram.WebApp.initDataUnsafe.user;
            if (user) {
                this.userId = user.id;
                document.getElementById('username').textContent = user.username || `User${user.id}`;
                
                // Check if user is premium
                if (user.is_premium) {
                    document.getElementById('premium-badge').style.display = 'inline';
                    this.boosters.multiplier *= 1.5; // Premium users get 50% bonus
                }
            }
        } else {
            console.log("Not running in Telegram environment");
            // Fallback for non-Telegram environment
            this.userId = 'demo-user';
        }
    }

    async loadGameConfig() {
        try {
            const response = await fetch('/api/spin/config', {
                headers: {
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.wheelSections = data.wheel_sections;
                this.playerBalance = data.user_balance || 0;
                this.spinCost = data.spin_cost || 0.2; // Default to 0.2 GC
                this.renderWheel();
            } else {
                console.error('Failed to load game config:', data.error);
                this.showError('Failed to load game configuration');
            }
        } catch (error) {
            console.error('Error loading game config:', error);
            this.showError('Network error. Please check your connection.');
        }
    }

    initializeElements() {
        // Get DOM elements
        this.wheel = document.getElementById('wheel');
        this.spinButton = document.getElementById('spin-button');
        this.cashoutButton = document.getElementById('cashout-button');
        this.balanceEl = document.getElementById('balance');
        this.spinsEl = document.getElementById('spins');
        this.totalWinningsEl = document.getElementById('total-winnings');
        this.resultEl = document.getElementById('result');
        this.resultText = document.getElementById('result-text');
        this.resultAmount = document.getElementById('result-amount');
        this.boosterIndicator = document.getElementById('booster-indicator');
        
        // Set initial values
        this.updateBalance();
        this.spinsEl.textContent = this.spinCount;
        this.totalWinningsEl.textContent = this.totalWinnings.toFixed(6);
    }

    setupEventListeners() {
        // Spin button
        this.spinButton.addEventListener('click', () => this.handleSpin());
        
        // Cashout button
        this.cashoutButton.addEventListener('click', () => this.handleCashout());
        
        // Buy extra spins button
        const buySpinsBtn = document.getElementById('buy-spins-btn');
        if (buySpinsBtn) {
            buySpinsBtn.addEventListener('click', () => this.openShop());
        }
        
        // Watch ad for free spin button
        const freeSpinBtn = document.getElementById('free-spin-btn');
        if (freeSpinBtn) {
            freeSpinBtn.addEventListener('click', () => this.watchAdForFreeSpin());
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
        
        // Check if user has free spins
        if (this.boosters.freeSpins > 0) {
            this.boosters.freeSpins--;
            this.updateBoosterIndicator();
            await this.performSpin();
            return;
        }
        
        // Check if user has enough balance
        if (this.playerBalance < this.spinCost) {
            this.showError('Insufficient balance');
            this.offerFreeSpin();
            return;
        }
        
        await this.performSpin();
    }

    async performSpin() {
        this.isSpinning = true;
        this.spinButton.disabled = true;
        
        try {
            // Deduct spin cost if not using free spin
            if (this.boosters.freeSpins <= 0) {
                this.playerBalance -= this.spinCost;
                this.updateBalance();
            }
            
            // Perform spin action
            const response = await fetch('/api/spin/action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                },
                body: JSON.stringify({
                    action: "spin",
                    use_free_spin: this.boosters.freeSpins > 0
                })
            });
            
            const data = await response.json();
            
            if (data.error) {
                this.showError(data.error);
                this.isSpinning = false;
                this.spinButton.disabled = false;
                
                // Refund the deducted amount
                if (this.boosters.freeSpins <= 0) {
                    this.playerBalance += this.spinCost;
                    this.updateBalance();
                }
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
                // Apply multiplier if available
                const actualWinnings = result.value * this.boosters.multiplier;
                
                this.playerBalance = data.new_balance || this.playerBalance;
                this.spinCount = data.spins || this.spinCount + 1;
                this.totalWinnings += actualWinnings;
                
                this.updateUI();
                
                this.resultText.textContent = result.id.toUpperCase();
                this.resultAmount.textContent = `${actualWinnings.toFixed(2)} GC`;
                this.resultEl.style.display = 'block';
                
                // Show floating reward
                this.showFloatingReward(actualWinnings);
                
                // Report spin completion to server
                this.reportSpinCompletion(actualWinnings);
                
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
            
            // Refund the deducted amount
            if (this.boosters.freeSpins <= 0) {
                this.playerBalance += this.spinCost;
                this.updateBalance();
            }
        }
    }

    async handleCashout() {
        try {
            const response = await fetch('/api/spin/cashout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                }
            });
            
            const data = await response.json();
            
            if (data.error) {
                this.showError(data.error);
                return;
            }
            
            // Show success message
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.showPopup({
                    title: "Cash Out Successful!",
                    message: `You've cashed out ${data.total_winnings.toFixed(6)} TON`,
                    buttons: [{
                        id: 'claim',
                        type: 'default',
                        text: 'Claim TON'
                    }]
                }, (btnId) => {
                    if (btnId === 'claim') {
                        window.Telegram.WebApp.sendData(JSON.stringify({
                            type: "claim_rewards",
                            game: "spin",
                            amount: data.total_winnings,
                            user_id: this.userId
                        }));
                    }
                });
            } else {
                alert(`Cash Out Successful! You've cashed out ${data.total_winnings.toFixed(6)} TON`);
            }
            
            // Reset game state
            this.totalWinnings = 0;
            this.updateUI();
            
        } catch (error) {
            console.error('Cashout error:', error);
            this.showError('Cashout failed. Please try again.');
        }
    }

    async checkActiveBoosters() {
        try {
            const response = await fetch('/api/user/boosters', {
                headers: {
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                data.boosters.forEach(booster => {
                    if (booster.game === 'spin' || booster.game === 'all') {
                        if (booster.type === 'multiplier') {
                            this.boosters.multiplier *= booster.value;
                        } else if (booster.type === 'extra_spins') {
                            this.boosters.freeSpins += booster.value;
                        }
                    }
                });
                
                this.updateBoosterIndicator();
            }
        } catch (error) {
            console.error('Error checking boosters:', error);
        }
    }

    updateBoosterIndicator() {
        if (!this.boosterIndicator) return;
        
        let boosterText = '';
        
        if (this.boosters.multiplier > 1) {
            boosterText += `${this.boosters.multiplier}x `;
        }
        
        if (this.boosters.freeSpins > 0) {
            boosterText += `${this.boosters.freeSpins} free spins `;
        }
        
        if (boosterText) {
            this.boosterIndicator.textContent = boosterText;
            this.boosterIndicator.style.display = 'block';
        } else {
            this.boosterIndicator.style.display = 'none';
        }
    }

    async checkDailyBonus() {
        try {
            const response = await fetch('/api/user/daily_bonus', {
                headers: {
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                }
            });
            
            const data = await response.json();
            
            if (data.success && data.available) {
                this.showDailyBonusPopup();
            }
        } catch (error) {
            console.error('Error checking daily bonus:', error);
        }
    }

    showDailyBonusPopup() {
        const bonusPopup = document.getElementById('daily-bonus-popup');
        if (bonusPopup) {
            bonusPopup.style.display = 'block';
            
            const claimButton = document.getElementById('claim-bonus');
            if (claimButton) {
                claimButton.onclick = () => this.claimDailyBonus();
            }
        }
    }

    async claimDailyBonus() {
        try {
            const response = await fetch('/api/user/claim_bonus', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Hide popup
                document.getElementById('daily-bonus-popup').style.display = 'none';
                
                // Update balance
                this.playerBalance = data.new_balance;
                this.updateBalance();
                
                // Show success message
                this.showToast(`Daily bonus claimed! +${data.bonus_amount} GC`);
            } else {
                this.showError(data.error || 'Failed to claim bonus');
            }
        } catch (error) {
            console.error('Error claiming bonus:', error);
            this.showError('Failed to claim bonus');
        }
    }

    offerFreeSpin() {
        // Show option to watch ad for free spin
        const freeSpinContainer = document.getElementById('free-spin-container');
        if (freeSpinContainer) {
            freeSpinContainer.style.display = 'block';
        }
    }

    async watchAdForFreeSpin() {
        try {
            // Show ad
            if (window.TelegramWebEvents) {
                const adWatched = await new Promise((resolve) => {
                    window.TelegramWebEvents.showAd('free_spin', (success) => {
                        resolve(success);
                    });
                });
                
                if (adWatched) {
                    // Grant free spin
                    this.boosters.freeSpins++;
                    this.updateBoosterIndicator();
                    
                    // Hide free spin container
                    document.getElementById('free-spin-container').style.display = 'none';
                    
                    this.showToast('Free spin granted!');
                } else {
                    this.showError('Ad not completed');
                }
            } else {
                // Fallback for non-Telegram environment
                this.boosters.freeSpins++;
                this.updateBoosterIndicator();
                document.getElementById('free-spin-container').style.display = 'none';
                this.showToast('Free spin granted!');
            }
        } catch (error) {
            console.error('Error watching ad:', error);
            this.showError('Failed to get free spin');
        }
    }

    openShop() {
        // Open shop to buy extra spins or boosters
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openTelegramLink('https://t.me/CryptoGamerShopBot');
        } else {
            // Fallback for non-Telegram environment
            window.open('/shop', '_blank');
        }
    }

    async reportSpinCompletion(value) {
        try {
            await fetch('/api/spin/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': window.Telegram?.WebApp?.initData || '',
                    'X-User-ID': this.userId
                },
                body: JSON.stringify({
                    winnings: value,
                    spins: this.spinCount
                })
            });
        } catch (error) {
            console.error('Spin completion report error:', error);
        }
    }

    updateUI() {
        this.updateBalance();
        this.spinsEl.textContent = this.spinCount;
        this.totalWinningsEl.textContent = this.totalWinnings.toFixed(6);
        
        // Update spin button text based on free spins
        if (this.boosters.freeSpins > 0) {
            this.spinButton.textContent = `SPIN (${this.boosters.freeSpins} FREE)`;
        } else {
            this.spinButton.textContent = `SPIN (${this.spinCost} GC)`;
        }
        
        // Enable/disable cashout button
        this.cashoutButton.disabled = this.totalWinnings <= 0;
    }

    updateBalance() {
        this.balanceEl.textContent = this.playerBalance.toFixed(2);
    }

    showFloatingReward(amount) {
        const floater = document.createElement('div');
        floater.className = 'reward-floater';
        floater.textContent = `+${amount.toFixed(2)} GC`;
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

    showError(message) {
        this.showToast(message, 'error');
    }

    showToast(message, type = 'info') {
        // Create toast element if it doesn't exist
        let toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            document.body.appendChild(toast);
        }
        
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
}

// Initialize the game when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.spinGame = new SpinGame();
});

// Add CSS for new elements
const style = document.createElement('style');
style.textContent = `
    .reward-floater {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: #4CAF50;
        font-weight: bold;
        font-size: 20px;
        pointer-events: none;
        z-index: 1000;
        animation: float-up 1s ease-out forwards;
    }
    
    @keyframes float-up {
        0% { transform: translate(-50%, -50%); opacity: 1; }
        100% { transform: translate(-50%, -150%); opacity: 0; }
    }
    
    .toast {
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 1000;
        opacity: 0;
        transition: opacity 0.3s;
        max-width: 80%;
        text-align: center;
    }
    
    .toast.show {
        opacity: 1;
    }
    
    .toast.error {
        background: rgba(244, 67, 54, 0.9);
    }
    
    .toast.success {
        background: rgba(76, 175, 80, 0.9);
    }
    
    #booster-indicator {
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(255, 215, 0, 0.2);
        border: 1px solid #FFD700;
        border-radius: 15px;
        padding: 5px 10px;
        font-size: 12px;
        color: #FFD700;
        display: none;
    }
    
    #free-spin-container {
        display: none;
        margin-top: 15px;
        text-align: center;
        padding: 10px;
        background: rgba(255, 215, 0, 0.1);
        border-radius: 10px;
        border: 1px solid rgba(255, 215, 0, 0.3);
    }
    
    #daily-bonus-popup {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.9);
        border: 2px solid #FFD700;
        border-radius: 15px;
        padding: 20px;
        z-index: 1000;
        text-align: center;
        display: none;
    }
    
    .game-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 15px;
        background: rgba(0, 0, 0, 0.5);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .header-balance {
        background: rgba(255, 215, 0, 0.2);
        border: 1px solid rgba(255, 215, 0, 0.5);
        border-radius: 15px;
        padding: 5px 10px;
        font-weight: bold;
    }
`;
document.head.appendChild(style);