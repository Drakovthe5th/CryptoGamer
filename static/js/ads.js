// ads.js - Ad functionality with Monetag integration
let adInProgress = false;

function loadAd() {
    fetch('/api/ads/available')
        .then(response => response.json())
        .then(ads => {
            if (ads.length > 0) {
                currentAd = ads[0];
                renderAd(currentAd);
            } else {
                document.getElementById('ad-container').innerHTML = 
                    '<p>No ads available at the moment</p>';
            }
        });
}

function renderAd(ad) {
    const adContainer = document.getElementById('ad-container');
    adContainer.innerHTML = `
        <div class="ad">
            <img src="${ad.image_url}" alt="${ad.title}">
            <h3>${ad.title}</h3>
            <p>${ad.description}</p>
            <p>Reward: ${ad.reward} TON</p>
        </div>
    `;
}

function showAd() {
    if (adInProgress) return;
    adInProgress = true;
    
    const button = document.getElementById('watch-ad-btn');
    if (button) {
        button.disabled = true;
        button.textContent = 'Loading ad...';
    }

    // Use Monetag's rewarded interstitial
    show_9644715().then(() => {
        // User completed the ad
        completeAd();
    }).catch(error => {
        console.error('Ad error:', error);
        Telegram.WebApp.showAlert('Failed to show ad or ad skipped.');
    }).finally(() => {
        if (button) {
            button.disabled = false;
            button.textContent = 'Watch Ad';
        }
        adInProgress = false;
    });
}

function completeAd() {
    fetch('/api/ads/reward', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ ad_id: 'monetag' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Telegram.WebApp.showAlert(`You earned ${data.reward} TON!`);
            loadUserData();
        } else {
            Telegram.WebApp.showAlert('Failed to reward ad: ' + data.error);
        }
    });

      // Track revenue
    fetch('/api/ads/revenue', {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({
        ad_id: 'monetag',
        type: 'interstitial'
        })
    });
    
}

// Monetag ad implementation
function loadMonetagAd() {
    const script = document.createElement('script');
    script.src = '//libtl.com/sdk.js';
    script.setAttribute('data-zone', '9644715');
    script.setAttribute('data-sdk', 'show_9644715');
    document.head.appendChild(script);
}

// A-ADS implementation
function loadAAds() {
    const aadsDiv = document.createElement('div');
    aadsDiv.innerHTML = `
        <div id="frame" style="width: 100%;">
            <iframe data-aa='2405512' src='//acceptable.a-ads.com/2405512' style='border:0px; padding:0; width:100%; height:100%; overflow:hidden; background-color: transparent;'></iframe>
            <a style="display: block; text-align: right; font-size: 12px" id="frame-link" href="https://aads.com/campaigns/new/?source_id=2405512&source_type=ad_unit&partner=2405512">Advertise here</a>
        </div>
    `;
    document.getElementById('ad-container').appendChild(aadsDiv);
}

// Add Telegram sponsored messages functionality
let telegramAds = [];

function loadTelegramAds() {
    fetch('/api/ads/telegram', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(ads => {
        if (ads && ads.messages) {
            telegramAds = ads.messages;
            renderTelegramAds();
        }
    });
}

function renderTelegramAds() {
    const container = document.getElementById('telegram-ads-container');
    if (!container || telegramAds.length === 0) return;
    
    telegramAds.forEach(ad => {
        const adElement = document.createElement('div');
        adElement.className = 'telegram-ad';
        adElement.innerHTML = `
            <h4>${ad.title}</h4>
            <p>${ad.message}</p>
            ${ad.photo ? `<img src="${ad.photo.url}" alt="${ad.title}">` : ''}
            <button onclick="handleTelegramAdClick('${ad.random_id}', '${ad.url}')">
                ${ad.button_text}
            </button>
        `;
        
        container.appendChild(adElement);
        
        // Record view after ad is rendered
        recordTelegramAdView(ad.random_id);
    });
}

function recordTelegramAdView(randomId) {
    fetch('/api/ads/telegram/view', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ random_id: randomId })
    });
}

function handleTelegramAdClick(randomId, url) {
    // Record click
    fetch('/api/ads/telegram/click', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ random_id: randomId })
    });
    
    // Open URL with confirmation for external links
    if (isExternalUrl(url)) {
        Telegram.WebApp.showConfirm(
            `Open external link: ${url}`,
            function(confirmed) {
                if (confirmed) window.open(url, '_blank');
            }
        );
    } else {
        window.open(url, '_blank');
    }
}

function isExternalUrl(url) {
    const telegramDomains = [
        'telegram.org', 't.me', 'telegra.ph', 
        'graph.org', 'fragment.com', 'telesco.pe'
    ];
    
    const hostname = new URL(url).hostname;
    return !telegramDomains.some(domain => hostname.endsWith(domain));
}

// Initialize ads
document.addEventListener('DOMContentLoaded', () => {
    loadAd();
    loadMonetagAd();
    loadAAds();
    loadTelegramAds();
    
    // Activate A-ADS after page load
    setTimeout(() => {
        const frame = document.getElementById('frame');
        if (frame) frame.style.display = 'block';
    }, 2000);
});