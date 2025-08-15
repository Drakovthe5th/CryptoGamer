document.addEventListener('DOMContentLoaded', function() {
    // Handle all action buttons
    document.querySelectorAll('[data-action]').forEach(button => {
        button.addEventListener('click', async function() {
            const action = this.dataset.action;
            const endpoint = this.dataset.endpoint;
            const amount = this.dataset.amount || '';
            
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ amount })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (data.new_balance) {
                        updateBalanceDisplay(data.new_balance);
                    }
                    showToast(`${action.replace('_', ' ')} successful!`);
                } else {
                    showToast(`Error: ${data.error || 'Action failed'}`, 'error');
                }
            } catch (error) {
                showToast('Network error. Please try again.', 'error');
                console.error('Action error:', error);
            }
        });
    });
    
    // Update balance display
    function updateBalanceDisplay(balance) {
        const balanceElements = document.querySelectorAll('.balance-display');
        balanceElements.forEach(el => {
            el.textContent = balance.toFixed(6) + ' TON';
        });
    }
    
    // Toast notification
    function showToast(message, type = 'success') {
        // Implement toast notifications here
        alert(`${type.toUpperCase()}: ${message}`);
    }
});