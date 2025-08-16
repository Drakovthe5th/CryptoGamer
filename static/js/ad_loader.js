class AdLoader {
    constructor() {
        this.slots = {
            'home_top_banner': { loaded: false },
            'home_bottom_banner': { loaded: false },
            'wallet_mid_banner': { loaded: false },
            'game_bottom_banner': { loaded: false },
            'quest_bottom_banner': { loaded: false }
        };
    }
    
    async loadSlot(slotId) {
        if (this.slots[slotId]?.loaded) return;
        
        try {
            const response = await fetch(`/api/ads/slot/${slotId}`);
            const adData = await response.json();
            
            if (adData.html) {
                const container = document.getElementById(slotId);
                if (container) {
                    if (adData.type === 'script') {
                        this._injectScript(adData.html, container);
                    } else {
                        container.innerHTML = adData.html;
                    }
                    this.slots[slotId].loaded = true;
                    
                    // Track ad view
                    fetch(`/api/ads/view/${slotId}`);
                }
            }
        } catch (error) {
            console.error(`Failed to load ad for ${slotId}:`, error);
        }
    }
    
    _injectScript(html, container) {
        const scriptContent = html.match(/<script>([\s\S]*?)<\/script>/)[1];
        const script = document.createElement('script');
        script.text = scriptContent;
        container.appendChild(script);
    }
    
    loadAllVisible() {
        Object.keys(this.slots).forEach(slotId => {
            const element = document.getElementById(slotId);
            if (element && this._isElementInViewport(element)) {
                this.loadSlot(slotId);
            }
        });
    }
    
    _isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
}

// Initialize ad loader
const adLoader = new AdLoader();

// Load ads when page is ready
document.addEventListener('DOMContentLoaded', () => {
    adLoader.loadAllVisible();
});

// Load ads when scrolling
window.addEventListener('scroll', () => {
    adLoader.loadAllVisible();
});

// API for showing rewarded ads
function showRewardedAd(slotName) {
    fetch(`/api/ads/show/${slotName}`)
        .then(response => response.json())
        .then(ad => {
            if (ad.html) {
                const modal = document.createElement('div');
                modal.className = 'ad-modal';
                modal.innerHTML = `
                    <div class="ad-modal-content">
                        <button class="close-ad">&times;</button>
                        <div id="rewarded-ad-container">${ad.html}</div>
                    </div>
                `;
                document.body.appendChild(modal);
                
                modal.querySelector('.close-ad').addEventListener('click', () => {
                    document.body.removeChild(modal);
                });
            }
        });
}

// Simple ad loader that doesn't make API calls
document.addEventListener('DOMContentLoaded', () => {
    const adSlots = document.querySelectorAll('.ad-slot');
    adSlots.forEach(slot => {
        slot.innerHTML = `
            <div style="width:100%;height:100%;background:#333;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;">
                <div style="text-align:center;color:#666;">
                    <div style="font-size:2rem;margin-bottom:8px;">📺</div>
                    <div>Ad Banner Placeholder</div>
                </div>
            </div>
        `;
    });
});