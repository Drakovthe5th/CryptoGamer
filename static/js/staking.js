// Staking Functions
function stakeTON() {
    const amount = parseFloat(document.getElementById('stake-amount').value);
    if (!amount || amount < 5) {
        alert('Minimum stake amount is 5 TON');
        return;
    }
    
    fetch('/api/staking/stake', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        },
        body: JSON.stringify({ amount })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Successfully staked ${amount} TON!`);
            updateStakingData();
        } else {
            alert('Staking failed: ' + data.error);
        }
    });
}

function updateStakingData() {
    fetch('/api/staking/data', {
        headers: {
            'X-Telegram-Hash': window.Telegram.WebApp.initData
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.staked) {
            document.getElementById('staked-amount').textContent = data.staked.toFixed(6);
        }
        if (data.rewards) {
            document.getElementById('staked-rewards').textContent = data.rewards.toFixed(6);
        }
    });
}

// Initialize staking data
document.addEventListener('DOMContentLoaded', updateStakingData);