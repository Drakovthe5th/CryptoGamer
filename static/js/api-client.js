// API Client - Minimal implementation
console.log('API Client loaded');

window.API = window.API || {
    call: async function(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Hash': window.Telegram ? Telegram.WebApp.initData : ''
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }
};