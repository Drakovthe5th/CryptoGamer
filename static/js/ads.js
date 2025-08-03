class AdManager {
    constructor(config) {
        this.userId = config.userId;
        this.country = config.country;
        this.config = config;
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
            <div id="coinzilla-ad" data-zone="${this.config.coinzillaZoneId}"></div>
        `;
    }
    
    loadPropellerAd() {
        if (!this.adScriptsLoaded.propeller) {
            const script = document.createElement('script');
            script.src = `https://ads.propellerads.com/v5/${this.config.propellerZoneId}`;
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
        const adContainer = document.getElementById('ad-container');
        adContainer.innerHTML = `
            <div id="frame" style="width: 100%; height: 100%;">
                <iframe data-aa='${this.config.aAdsZoneId}' 
                        src='//acceptable.a-ads.com/${this.config.aAdsZoneId}' 
                        style='border:0px; padding:0; width:100%; height:100%; overflow:hidden; background-color: transparent;'>
                </iframe>
                <a style="display: block; text-align: right; font-size: 12px" 
                   href="https://aads.com/campaigns/new/?source_id=${this.config.aAdsZoneId}&source_type=ad_unit&partner=${this.config.aAdsZoneId}">
                   Advertise here
                </a>
            </div>
        `;
    }
    
    // Rewarded ad flow
    showRewardedAd() {
        const boostButton = document.getElementById('boost-earnings');
        const originalText = boostButton.innerHTML;
        boostButton.innerHTML = 'Loading ad...';
        boostButton.disabled = true;
        
        // Show Monetag rewarded ad
        show_9644715('pop').then(() => {
            // User watched ad till the end
            this.grantReward('monetag');
            boostButton.innerHTML = originalText;
            boostButton.disabled = false;
        }).catch(error => {
            console.error('Ad error:', error);
            boostButton.innerHTML = originalText;
            boostButton.disabled = false;
        });
    }
    
    // Show interstitial ad
    showInterstitialAd() {
        show_9644715({
            type: 'inApp',
            inAppSettings: {
                frequency: 2,
                capping: 0.1,
                interval: 30,
                timeout: 5,
                everyPage: false
            }
        });
    }
    
    grantReward(platform) {
        fetch('/api/ads/reward', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-User-ID': this.userId.toString()
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