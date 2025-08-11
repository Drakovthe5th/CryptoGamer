class Miniapp {
    static init(telegramInitData) {
        this.initData = telegramInitData;
        this.securityToken = this.generateSecurityToken();
        this.userData = {
            id: null,
            username: 'Guest',
            balance: 0,
            clicks: 0,
            referrals: 0,
            refEarnings: 0,
            bonusClaimed: false
        };
    }

    static generateSecurityToken() {
        const token = Math.random().toString(36).substring(2, 15);
        const timestamp = Math.floor(Date.now() / 1000);
        return btoa(`${token}:${timestamp}`);
    }

    static async apiRequest(endpoint, method = 'GET', body = null) {
        const headers = {
            'X-Telegram-Init-Data': this.initData,
            'X-Security-Token': this.securityToken
        };
        
        if (body) {
            headers['Content-Type'] = 'application/json';
        }
        
        try {
            const options = {
                method,
                headers,
                credentials: 'include'
            };
            
            if (body) {
                options.body = JSON.stringify(body);
            }
            
            const response = await fetch(endpoint, options);
            
            if (response.status === 403) {
                document.getElementById('security-alert').style.display = 'block';
                Telegram.WebApp.showAlert('Account restricted. Contact support.');
                return null;
            }
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'API request failed');
            }
            
            return await response.json();
        } catch (error) {
            Telegram.WebApp.showAlert(error.message || 'Request failed');
            throw error;
        }
    }

    static async loadUserData() {
        try {
            const response = await this.apiRequest(`/api/user/secure-data?user_id=${this.userData.id}`);
            if (response && response.token) {
                const userData = this.parseJwt(response.token);
                this.userData = {
                    ...this.userData,
                    username: userData.username,
                    balance: userData.balance,
                    clicks: userData.clicks_today,
                    referrals: userData.referrals,
                    refEarnings: userData.ref_earnings,
                    bonusClaimed: userData.bonus_claimed
                };
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to load user data:', error);
        }
    }

    static parseJwt(token) {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => 
                '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));

            return JSON.parse(jsonPayload);
        } catch (e) {
            return null;
        }
    }

    static updateUI() {
        document.querySelectorAll('#balance, #wallet-balance, #profile-balance').forEach(el => {
            el.textContent = this.userData.balance.toFixed(2);
        });
        
        document.getElementById('click-count').textContent = this.userData.clicks;
        document.getElementById('quest-ads').textContent = "0"; // Would come from quest data
        document.getElementById('quest-invite').textContent = this.userData.referrals > 0 ? "1" : "0";
        document.getElementById('ref-count').textContent = this.userData.referrals;
        document.getElementById('ref-earnings').textContent = this.userData.refEarnings.toFixed(2);
        
        document.querySelectorAll('#profile-username, #profile-name').forEach(el => {
            el.textContent = this.userData.username;
        });
        
        // Update bonus button based on claim status
        const bonusBtn = document.querySelector('#home-page .btn');
        if (bonusBtn) {
            if (this.userData.bonusClaimed) {
                bonusBtn.textContent = '✅ Bonus Claimed';
                bonusBtn.disabled = true;
            } else {
                bonusBtn.textContent = '🎁 Claim 0.05 TON';
                bonusBtn.disabled = false;
            }
        }
    }

    static async claimDailyBonus() {
        try {
            const response = await this.apiRequest('/api/quests/claim_bonus', 'POST', {
                user_id: this.userData.id
            });
            
            if (response && response.success) {
                this.userData.balance = response.new_balance;
                this.userData.bonusClaimed = true;
                this.updateUI();
                
                Telegram.WebApp.showPopup({
                    title: 'Bonus Claimed!', 
                    message: '+0.05 TON added to your balance',
                    buttons: [{id: 'ok', type: 'ok'}]
                });
            }
        } catch (error) {
            console.error('Failed to claim bonus:', error);
        }
    }

    static async earnFromClick() {
        try {
            if (this.userData.clicks >= 100) {
                Telegram.WebApp.showPopup({
                    title: 'Limit Reached!',
                    message: 'Try again tomorrow',
                    buttons: [{id: 'ok', type: 'ok'}]
                });
                return;
            }
            
            const response = await this.apiRequest('/api/quests/record_click', 'POST', {
                user_id: this.userData.id
            });
            
            if (response) {
                this.userData.clicks = response.clicks;
                this.userData.balance = response.balance;
                this.updateUI();
                
                // Visual feedback
                const clickArea = document.querySelector('.click-area');
                if (clickArea) {
                    clickArea.style.transform = 'scale(0.95)';
                    setTimeout(() => clickArea.style.transform = 'scale(1)', 120);
                }
            }
        } catch (error) {
            console.error('Failed to record click:', error);
        }
    }

    static async rewardedInterstitial() {
        try {
            // Show ad using Monetag SDK
            await show_9644715();
            
            const response = await this.apiRequest('/api/ads/reward', 'POST', {
                user_id: this.userData.id,
                ad_id: 'monetag_9644715'
            });
            
            if (response) {
                this.userData.balance = response.new_balance;
                this.updateUI();
                
                Telegram.WebApp.showPopup({
                    title: 'Ad Watched!', 
                    message: `+${response.reward.toFixed(2)} TON added to your balance`,
                    buttons: [{id: 'ok', type: 'ok'}]
                });
            }
        } catch (error) {
            console.error('Failed to show ad:', error);
            Telegram.WebApp.showPopup({
                title: 'Ad Error', 
                message: 'Failed to show ad. Please try again.',
                buttons: [{id: 'ok', type: 'ok'}]
            });
        }
    }

    static async generateReferralLink() {
        try {
            const response = await this.apiRequest(`/api/referral/generate?user_id=${this.userData.id}`);
            if (response && response.success) {
                document.getElementById('ref-link').textContent = response.referral_link;
                return response.referral_link;
            }
        } catch (error) {
            console.error('Failed to generate referral:', error);
        }
        return null;
    }

    static async getReferralStats() {
        try {
            const response = await this.apiRequest(`/api/referral/stats?user_id=${this.userData.id}`);
            if (response && response.success) {
                this.userData.referrals = response.referrals;
                this.userData.refEarnings = response.ref_earnings;
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to get referral stats:', error);
        }
    }

    static async getOTCRates() {
        try {
            const response = await this.apiRequest('/api/otc/rates');
            if (response && response.success) {
                return response.rates;
            }
        } catch (error) {
            console.error('Failed to get OTC rates:', error);
        }
        return null;
    }

    static async createStaking(amount) {
        try {
            const response = await this.apiRequest('/api/staking/create', 'POST', {
                user_id: this.userData.id,
                amount: amount
            });
            
            if (response && response.success) {
                Telegram.WebApp.showPopup({
                    title: 'Staking Created!', 
                    message: `${amount} TON staked successfully`,
                    buttons: [{id: 'ok', type: 'ok'}]
                });
                return true;
            }
        } catch (error) {
            console.error('Failed to create staking:', error);
        }
        return false;
    }
}

// Initialize the app
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        // Initialize Miniapp with Telegram data
        Miniapp.init(tg.initData);
        
        // Get user ID from Telegram
        Miniapp.userData.id = tg.initDataUnsafe.user?.id;
        if (!Miniapp.userData.id) throw new Error('User ID missing');
        
        // Load user data
        await Miniapp.loadUserData();
        
        // Generate referral link
        await Miniapp.generateReferralLink();
        
        // Get referral stats
        await Miniapp.getReferralStats();
        
        // Get OTC rates
        const rates = await Miniapp.getOTCRates();
        if (rates) {
            document.querySelectorAll('#otc-page p').forEach((el, i) => {
                if (i === 0) el.textContent = `1 TON = $${rates.USD} USD`;
                if (i === 1) el.textContent = `1 TON = ${rates.KES} KES`;
            });
        }
        
        // Show welcome message
        tg.showPopup({
            title: 'Welcome!', 
            message: `Let's earn TON, ${Miniapp.userData.username}!`,
            buttons: [{id: 'ok', type: 'ok'}]
        });
        
        // Set up event handlers
        document.querySelector('#home-page .btn')?.addEventListener('click', Miniapp.claimDailyBonus.bind(Miniapp));
        document.querySelector('.click-area')?.addEventListener('click', Miniapp.earnFromClick.bind(Miniapp));
        document.querySelector('#watch-page .btn')?.addEventListener('click', Miniapp.rewardedInterstitial.bind(Miniapp));
        document.querySelector('#wallet-page .btn')?.addEventListener('click', () => {
            Miniapp.createStaking(5);
        });
        document.querySelector('#referrals-page button.btn')?.addEventListener('click', () => {
            navigator.clipboard.writeText(document.getElementById('ref-link').textContent);
            tg.showPopup({
                title: 'Copied', 
                message: 'Referral link copied',
                buttons: [{id: 'ok', type: 'ok'}]
            });
        });
        
    } catch (error) {
        console.error('Initialization failed:', error);
        Telegram.WebApp.showAlert('Failed to initialize app. Please try again.');
    }
});