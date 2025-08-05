let currentAd = null;

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
    if (!currentAd) {
        alert('No ad available');
        return;
    }
    
    // Show ad in fullscreen
    document.getElementById('ad-container').classList.add('fullscreen');
    
    // Start ad timer
    let timeLeft = 30;
    const timer = setInterval(() => {
        timeLeft--;
        document.getElementById('watch-ad-btn').textContent = `Watching (${timeLeft}s)`;
        
        if (timeLeft <= 0) {
            clearInterval(timer);
            completeAd();
        }
    }, 1000);
}

function completeAd() {
    fetch('/api/ads/reward', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ ad_id: currentAd.id })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`You earned ${data.reward} TON!`);
            updateBalance(data.new_balance);
        } else {
            alert('Failed to reward ad: ' + data.error);
        }
        document.getElementById('ad-container').classList.remove('fullscreen');
        document.getElementById('watch-ad-btn').textContent = 'Watch Ad';
        loadAd(); // Load next ad
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', loadAd);