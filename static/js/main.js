// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;

// Check user authentication
if (!tg.initDataUnsafe.user || !tg.initDataUnsafe.user.id) {
    document.getElementById('app').innerHTML = 
        '<div class="error">Error: User authentication failed</div>';
    throw new Error("User ID not available");
}

// DOM elements
const balanceDisplay = document.getElementById('balance');
const minWithdrawalDisplay = document.getElementById('min-withdrawal');
const questsContainer = document.getElementById('quests-container');
const adContainer = document.getElementById('ad-container');

// Basic HTML escaping for security
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[tag]));
}

// Format balance display
function formatBalance(balance) {
    return parseFloat(balance).toFixed(6) + ' XNO';
}

// Load user data
async function loadUserData() {
    try {
        questsContainer.innerHTML = '<div class="loading">Loading quests...</div>';
        
        const response = await fetch('/api/user/data', {
            headers: {
                'X-Telegram-User-ID': tg.initDataUnsafe.user.id.toString(),
                'X-Telegram-Hash': tg.initData
            }
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update balance
        balanceDisplay.textContent = formatBalance(data.balance);
        
        // Update min withdrawal
        minWithdrawalDisplay.textContent = formatBalance(data.min_withdrawal);
        
        // Update quests
        renderQuests(data.quests);
        
        // Update ads
        renderAd(data.ads[0]);
        
    } catch (error) {
        console.error("Failed to load user data:", error);
        balanceDisplay.textContent = '0.000000 XNO';
        questsContainer.innerHTML = `<div class="error">${error.message || 'Error loading data'}</div>`;
    }
}

// Render quests
function renderQuests(quests) {
    questsContainer.innerHTML = '';
    
    if (!quests || quests.length === 0) {
        questsContainer.innerHTML = '<div class="loading">No active quests available</div>';
        return;
    }
    
    quests.forEach(quest => {
        const questEl = document.createElement('div');
        questEl.className = 'quest-item';
        questEl.innerHTML = `
            <div class="quest-icon">🎯</div>
            <div class="quest-details">
                <div class="quest-title">${escapeHtml(quest.title)}</div>
                <div class="quest-reward">Reward: ${quest.reward.toFixed(6)} XNO</div>
            </div>
            <div class="quest-status ${quest.completed ? 'completed' : ''}">
                ${quest.completed ? '✅ Completed' : '🔄 Active'}
            </div>
        `;
        questsContainer.appendChild(questEl);
    });
}

// Render ad
function renderAd(ad) {
    if (!ad) {
        adContainer.innerHTML = '<div class="loading">No ads available</div>';
        return;
    }
    
    adContainer.innerHTML = `
        <img src="${ad.image_url}" class="ad-image" alt="${escapeHtml(ad.title)}">
        <div class="ad-title">${escapeHtml(ad.title)}</div>
        <button class="ad-button" onclick="claimAdReward('${ad.id}')">
            View Ad (+${ad.reward.toFixed(6)} XNO)
        </button>
    `;
}

// Claim ad reward
window.claimAdReward = async (adId) => {
    try {
        const response = await fetch('/api/ads/reward', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-User-ID': tg.initDataUnsafe.user.id.toString(),
                'X-Telegram-Hash': tg.initData
            },
            body: JSON.stringify({ ad_id: adId })
        });
        
        const result = await response.json();
        
        if (result.error) {
            throw new Error(result.error);
        }
        
        alert(`🎉 You earned ${result.reward.toFixed(6)} XNO!`);
        loadUserData(); // Refresh data
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
};

// Initialize
tg.ready();
tg.expand();