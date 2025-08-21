#!/bin/bash
# render-build.sh

echo "Starting Render build process..."

# Create missing directories if they don't exist
mkdir -p static/images
mkdir -p static/js
mkdir -p static/css

# Create default avatar if it doesn't exist
if [ ! -f static/images/default-avatar.png ]; then
    echo "Creating default avatar..."
    convert -size 100x100 xc:blue static/images/default-avatar.png || echo "Using fallback avatar"
fi

# Create favicon if it doesn't exist
if [ ! -f static/favicon.ico ]; then
    echo "Creating favicon..."
    convert -size 16x16 xc:blue static/favicon.ico || echo "Using fallback favicon"
fi

# Create missing JS files
if [ ! -f static/js/state-manager.js ]; then
    echo "Creating state-manager.js..."
    cat > static/js/state-manager.js << 'EOL'
// Minimal state management
window.StateManager = {
    state: {},
    setState: function(newState) {
        this.state = {...this.state, ...newState};
    },
    getState: function() {
        return this.state;
    }
};
EOL
fi

if [ ! -f static/js/api-client.js ]; then
    echo "Creating api-client.js..."
    cat > static/js/api-client.js << 'EOL'
// Basic API client
window.API = {
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
EOL
fi

if [ ! -f static/js/components.js ]; then
    echo "Creating components.js..."
    cat > static/js/components.js << 'EOL'
// Basic components
window.Components = {
    showToast: function(message, type = 'info') {
        if (window.Telegram && Telegram.WebApp) {
            Telegram.WebApp.showPopup({
                title: type.charAt(0).toUpperCase() + type.slice(1),
                message: message,
                buttons: [{type: 'ok'}]
            });
        } else {
            alert(message);
        }
    }
};
EOL
fi

echo "Build process completed!"