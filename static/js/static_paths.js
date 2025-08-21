// static_paths.js - Central configuration for all static asset paths
window.StaticPaths = {
    // Global assets (from root /static/)
    global: {
        css: {
            main: '/static/css/main.css',
            miniapp: '/static/css/miniapp.css',
            admin: '/static/css/admin.css'
        },
        js: {
            main: '/static/js/main.js',
            websocket: '/static/js/websocket.js',
            charts: '/static/js/charts.js',
            staking: '/static/js/staking.js',
            ads: '/static/js/ads.js',
            miniapp: '/static/js/miniapp.js'
        },
        images: '/static/images/',
        icons: '/static/icons/',
        manifest: '/static/manifest.json',
        favicon: '/static/favicon.ico'
    },
    
    // Game assets (from /games/static/ via /game-assets/ route)
    games: {
        base: '/game-assets/',
        html: '/games/',
        getCSS: (game) => `/game-assets/${game}/style.css`,
        getJS: (game) => `/game-assets/${game}/game.js`,
        getAssets: (game, filename) => `/game-assets/${game}/assets/${filename}`,
        
        // Game-specific paths
        clicker: {
            css: '/game-assets/clicker/style.css',
            js: '/game-assets/clicker/game.js'
        },
        trivia: {
            css: '/game-assets/trivia/trivia.css',
            js: '/game-assets/trivia/trivia.js'
        },
        trex: {
            css: '/game-assets/trex/trex.css',
            js: '/game-assets/trex/trex.js'
        },
        spin: {
            css: '/game-assets/spin/spin.css',
            js: '/game-assets/spin/spin.js'
        },
        edge_surf: {
            css: '/game-assets/edge-surf/surf.css',
            js: '/game-assets/edge-surf/surf.js'
        }
    },
    
    // Validation function
    isValidGame: (game) => {
        const validGames = ['clicker', 'trivia', 'trex', 'spin', 'edge-surf'];
        return validGames.includes(game);
    },
    
    // Utility function to load game assets
    loadGameAssets: function(gameType) {
        if (!this.isValidGame(gameType)) {
            console.error(`Invalid game type: ${gameType}`);
            return false;
        }
        
        // Enable game-specific CSS
        document.querySelectorAll('[id$="-css"]').forEach(css => {
            css.disabled = true;
        });
        
        const gameCSS = document.getElementById(`${gameType}-css`);
        if (gameCSS) {
            gameCSS.disabled = false;
            console.log(`Enabled CSS for ${gameType}`);
        }
        
        // Load game JavaScript
        if (!window.gameScripts) window.gameScripts = {};
        
        if (!window.gameScripts[gameType]) {
            const script = document.createElement('script');
            script.src = this.games[gameType].js;
            script.onload = () => {
                window.gameScripts[gameType] = true;
                console.log(`Loaded JS for ${gameType}`);
            };
            script.onerror = () => {
                console.error(`Failed to load JS for ${gameType}`);
            };
            document.head.appendChild(script);
        }
        
        return true;
    }
};

// Make it available globally
console.log('StaticPaths configuration loaded');