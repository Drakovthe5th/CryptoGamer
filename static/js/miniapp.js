// miniapp.js - Mini App specific functionality
document.addEventListener('DOMContentLoaded', function() {
    // Set up navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const pageId = this.dataset.page;
            showPage(pageId);
        });
    });
    
    // Initialize referral link
    const userId = Telegram.WebApp.initData.user?.id || 'user123';
    const refElements = document.querySelectorAll('#ref-link');
    refElements.forEach(el => {
        el.value = `https://t.me/Got3dBot?start=${userId}`;
    });
    
    // Load initial page
    showPage('home');
});

function claimDailyBonus() {
    fetch('/api/user/claim-daily', {
        method: 'POST',
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Telegram.WebApp.showPopup({
                title: 'Daily Bonus Claimed!',
                message: `You received ${data.reward} TON`,
            });
            loadUserData();
        }
    });
}

function earnFromClick() {
    fetch('/api/earn/click', {
        method: 'POST',
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('click-count').textContent = data.clicks;
            loadUserData();
            
            // Visual feedback
            const clickArea = document.querySelector('.click-area');
            clickArea.style.transform = 'scale(0.95)';
            setTimeout(() => {
                clickArea.style.transform = 'scale(1)';
            }, 100);
        } else {
            Telegram.WebApp.showPopup({
                title: 'Daily Limit Reached',
                message: 'Come back tomorrow for more clicks!',
            });
        }
    });
}

function playGame(gameType) {
    fetch(`/api/games/start?game=${gameType}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Telegram.WebApp.showPopup({
                title: 'Game Starting',
                message: 'Good luck!',
            });
        } else {
            Telegram.WebApp.showAlert('Failed to start game: ' + data.error);
        }
    });
}

function copyReferralLink() {
    const refLink = document.getElementById('ref-link');
    refLink.select();
    document.execCommand('copy');
    Telegram.WebApp.showPopup({
        title: 'Link Copied!',
        message: 'Referral link copied to clipboard',
    });
}