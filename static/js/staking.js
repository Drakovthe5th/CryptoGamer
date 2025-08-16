// Updated stakeTON function
async function stakeTON() {
  const amount = parseFloat(document.getElementById('stake-amount').value);
  
  try {
    const response = await fetch('/api/staking/stake', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Hash': window.Telegram.WebApp.initData
      },
      body: JSON.stringify({ amount })
    });
    
    const data = await response.json();
    
    if (data.success) {
      if (data.transaction) {
        // Execute on blockchain
        const result = await window.ton.sendTransaction({
          to: data.contract,
          value: data.value,
          data: data.payload
        });
        
        if (result) {
          updateStakingData();
          showToast(`Staked ${amount} TON! TX: ${result.hash}`);
        }
      }
    } else {
      showToast(`Error: ${data.error}`, 'error');
    }
  } catch (error) {
    showToast('Blockchain error. Please try again.', 'error');
    console.error('Staking error:', error);
  }
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