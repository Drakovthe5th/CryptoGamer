// Components - Minimal implementation
console.log('Components loaded');

window.Components = window.Components || {
    showToast: function(message, type = 'info') {
        if (window.Telegram && Telegram.WebApp) {
            Telegram.WebApp.showPopup({
                title: type.charAt(0).toUpperCase() + type.slice(1),
                message: message,
                buttons: [{ type: 'ok' }]
            });
        } else {
            alert(message);
        }
    },
    
    showSpinner: function() {
        const spinner = document.getElementById('global-spinner');
        if (spinner) {
            spinner.style.display = 'flex';
        }
    },
    
    hideSpinner: function() {
        const spinner = document.getElementById('global-spinner');
        if (spinner) {
            spinner.style.display = 'none';
        }
    }
};

function updateCrewCreditsDisplay(credits) {
    document.getElementById('crew-credits').textContent = credits;
    
    // Enable/disable join button based on credits
    const joinButton = document.getElementById('btn-join-game');
    if (joinButton) {
        joinButton.disabled = credits < 100; // Entry fee
    }
}