class AdManager {
    constructor({ userId, country }) {
        this.userId = userId;
        this.country = country;
        this.adBlockDetected = false;
        this.adScriptsLoaded = {};
        this.checkAdBlock();
    }
    
    // Ad block detection
    checkAdBlock() {
        const testAd = document.createElement('div');
        testAd.innerHTML = '&nbsp;';
        testAd.className = 'adsbox';
        document.body.appendChild(testAd);
        
        setTimeout(() => {
            if (testAd.offsetHeight === 0) {
                this.adBlockDetected = true;
                this.handleAdBlock();
            }
            document.body.removeChild(testAd);
        }, 100);
    }
    
    handleAdBlock() {
        const adContainer = document.getElementById('ad-container');
        adContainer.innerHTML = `
            <div class="ad-alternative">
                <p>Ad blocker detected. Support us by enabling ads!</p>
                <button onclick="location.reload()">Reload with Ads</button>
            </div>
        `;
    }
    
    // Geo-targeted ad selection
    selectAdPlatform() {
        // High CPM countries get premium ads
        const highCPMCountries = ['US', 'CA', 'UK', 'AU', 'DE', 'FR'];
        if (highCPMCountries.includes(this.country)) {
            return 'coinzilla';
        }
        
        // Crypto-focused countries
        const cryptoCountries = ['RU', 'UA', 'TR', 'VN', 'BR', 'IN'];
        if (cryptoCountries.includes(this.country)) {
            return 'a-ads';
        }
        
        // Default to PropellerAds
        return 'propeller';
    }
    
    // Load ad implementation
    loadAd() {
        if (this.adBlockDetected) return;
        
        const platform = this.selectAdPlatform();
        const adContainer = document.getElementById('ad-container');
        
        // Clear previous ad
        adContainer.innerHTML = '';
        
        switch(platform) {
            case 'coinzilla':
                this.loadCoinzillaAd();
                break;
                
            case 'propeller':
                this.loadPropellerAd();
                break;
                
            case 'a-ads':
                this.loadAAdsAd();
                break;
        }
        
        this.trackImpression(platform, 'banner');
    }
    
    loadCoinzillaAd() {
        if (!this.adScriptsLoaded.coinzilla) {
            const script = document.createElement('script');
            script.src = 'https://coinzilla.com/scripts/banner.js';
            script.async = true;
            document.head.appendChild(script);
            this.adScriptsLoaded.coinzilla = true;
        }
        
        const adContainer = document.getElementById('ad-container');
        adContainer.innerHTML = `
            <div id="coinzilla-ad" data-zone="${config.COINZILLA_ZONE_ID}"></div>
        `;
    }
    
    loadPropellerAd() {
        if (!this.adScriptsLoaded.propeller) {
            const script = document.createElement('script');
            script.src = `https://ads.propellerads.com/v5/${config.PROPELLER_ZONE_ID}`;
            script.async = true;
            document.head.appendChild(script);
            this.adScriptsLoaded.propeller = true;
        }
        
        const adContainer = document.getElementById('ad-container');
        adContainer.innerHTML = `
            <div id="propeller-ad"></div>
        `;
    }
    
    loadAAdsAd() {
        if (!this.adScriptsLoaded.aads) {
            const script = document.createElement('script');
            script.src = `https://a-ads.com/${config.A_ADS_ZONE_ID}`;
            script.async = true;
            document.head.appendChild(script);
            this.adScriptsLoaded.aads = true;
        }
        
        const adContainer = document.getElementById('ad-container');
        adContainer.innerHTML = `
            <div id="a-ads-ad"></div>
        `;
    }
    
    // Rewarded ad flow
    showRewardedAd() {
        const platform = this.selectAdPlatform();
        
        // Show loading indicator
        const boostButton = document.getElementById('boost-earnings');
        const originalText = boostButton.innerHTML;
        boostButton.innerHTML = 'Loading ad...';
        boostButton.disabled = true;
        
        switch(platform) {
            case 'coinzilla':
                return this.showCoinzillaRewarded(originalText);
                
            case 'propeller':
                return this.showPropellerRewarded(originalText);
                
            case 'a-ads':
                return this.showAAdsRewarded(originalText);
        }
    }
    
    showCoinzillaRewarded(originalText) {
        return new Promise((resolve, reject) => {
            // Simulated rewarded ad flow
            Telegram.WebApp.showAlert('Watch a short video to earn rewards!');
            
            // Simulate ad loading time
            setTimeout(() => {
                // Simulate ad completion
                setTimeout(() => {
                    this.grantReward('coinzilla');
                    resolve();
                    
                    // Reset button
                    const boostButton = document.getElementById('boost-earnings');
                    boostButton.innerHTML = originalText;
                    boostButton.disabled = false;
                }, 3000);
            }, 1500);
        });
    }
    
    showPropellerRewarded(originalText) {
        return new Promise((resolve, reject) => {
            // Simulated rewarded ad flow
            Telegram.WebApp.showAlert('Complete the ad to earn rewards!');
            
            setTimeout(() => {
                setTimeout(() => {
                    this.grantReward('propeller');
                    resolve();
                    
                    // Reset button
                    const boostButton = document.getElementById('boost-earnings');
                    boostButton.innerHTML = originalText;
                    boostButton.disabled = false;
                }, 3000);
            }, 1500);
        });
    }
    
    showAAdsRewarded(originalText) {
        return new Promise((resolve, reject) => {
            // Simulated rewarded ad flow
            Telegram.WebApp.showAlert('Watch the full ad to earn crypto!');
            
            setTimeout(() => {
                setTimeout(() => {
                    this.grantReward('a-ads');
                    resolve();
                    
                    // Reset button
                    const boostButton = document.getElementById('boost-earnings');
                    boostButton.innerHTML = originalText;
                    boostButton.disabled = false;
                }, 3000);
            }, 1500);
        });
    }
    
    grantReward(platform) {
        fetch('/miniapp/ad-reward', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-User': this.userId
            },
            body: JSON.stringify({ 
                platform: platform,
                country: this.country
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const message = `You earned ${data.reward.toFixed(6)} XNO! ${data.weekend_boost ? '(Weekend Boost Active!)' : ''}`;
                Telegram.WebApp.showAlert(message);
                Telegram.WebApp.HapticFeedback.impactOccurred('heavy');
                
                // Update balance display
                const balanceDisplay = document.querySelector('.balance-amount');
                if (balanceDisplay) {
                    const currentBalance = parseFloat(balanceDisplay.textContent);
                    balanceDisplay.textContent = (currentBalance + data.reward).toFixed(6) + ' XNO';
                }
            }
        });
    }
    
    // Ad refresh
    refreshAd() {
        if (this.adBlockDetected) return;
        this.loadAd();
    }
    
    // Performance tracking
    trackImpression(platform, adType) {
        fetch('/ad-impression', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                platform: platform,
                ad_type: adType,
                country: this.country,
                user_id: this.userId
            })
        });
    }
}

// Initialize AdManager for global access
window.AdManager = AdManager;