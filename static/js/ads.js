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
  if (adInProgress) return;
  adInProgress = true;
  
  const button = document.getElementById('watch-ad-btn');
  button.disabled = true;
  button.textContent = 'Loading ad...';

  // Use Monetag's rewarded interstitial
  show_9644715().then(() => {
    // User completed the ad
    completeAd();
  }).catch(error => {
    console.error('Ad error:', error);
    alert('Failed to show ad or ad skipped.');
  }).finally(() => {
    button.disabled = false;
    button.textContent = 'Watch Ad';
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
    body: JSON.stringify({ ad_id: 'monetag' }) // Special ID for Monetag ads
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      alert(`You earned ${data.reward} TON!`);
      updateBalance(data.new_balance);
    } else {
      alert('Failed to reward ad: ' + data.error);
    }
  });
}

// ads.js - alternative showAdPopup function
function showAdPopup() {
  if (adInProgress) return;
  adInProgress = true;
  
  const button = document.getElementById('watch-ad-btn');
  button.disabled = true;
  button.textContent = 'Loading ad...';

  // Use Monetag's rewarded popup
  show_9644715('pop').then(() => {
    // User completed the ad
    completeAd();
  }).catch(error => {
    console.error('Ad error:', error);
  }).finally(() => {
    button.disabled = false;
    button.textContent = 'Watch Ad';
    adInProgress = false;
  });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadAd();
  
  // Activate A-ADS after page load
  setTimeout(() => {
    document.getElementById('frame').style.display = 'block';
  }, 2000);
});

// Initialize
document.addEventListener('DOMContentLoaded', loadAd);