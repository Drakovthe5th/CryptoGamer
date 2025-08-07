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
}

// Initialize ads
document.addEventListener('DOMContentLoaded', () => {
    loadAd();
    
    // Activate A-ADS after page load
    setTimeout(() => {
        const frame = document.getElementById('frame');
        if (frame) frame.style.display = 'block';
    }, 2000);
});