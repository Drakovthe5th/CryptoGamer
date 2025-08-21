// static_paths.js - Enhanced for Render compatibility
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
        
        // Game-specific paths with fallbacks
        clicker: {
            css: '/game-assets/clicker/style.css',
            js: '/game-assets/clicker/game.js',
            fallback: true // Indicates this is a critical game
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
    
    // Cache management for Render performance
    cache: {
        enabled: true,
        version: 'v1.0',
        getCacheKey: (url) => {
            return `${url}?v=${this.cache.version}`;
        }
    },
    
    // Validation function
    isValidGame: (game) => {
        const validGames = ['clicker', 'trivia', 'trex', 'spin', 'edge-surf'];
        return validGames.includes(game);
    },
    
    // Utility function to load game assets with retry logic
    loadGameAssets: function(gameType, retries = 3) {
        if (!this.isValidGame(gameType)) {
            console.error(`Invalid game type: ${gameType}`);
            return Promise.reject(new Error(`Invalid game type: ${gameType}`));
        }
        
        return new Promise((resolve, reject) => {
            const attemptLoad = (attempt = 1) => {
                try {
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
                        
                        // Add cache busting for Render
                        const scriptUrl = this.cache.enabled ? 
                            this.cache.getCacheKey(this.games[gameType].js) : 
                            this.games[gameType].js;
                            
                        script.src = scriptUrl;
                        
                        script.onload = () => {
                            window.gameScripts[gameType] = true;
                            console.log(`Loaded JS for ${gameType}`);
                            resolve(true);
                        };
                        
                        script.onerror = () => {
                            if (attempt < retries) {
                                console.warn(`Retry ${attempt}/${retries} for ${gameType} JS`);
                                setTimeout(() => attemptLoad(attempt + 1), 1000 * attempt);
                            } else {
                                console.error(`Failed to load JS for ${gameType} after ${retries} attempts`);
                                
                                // Try fallback to CDN if available
                                if (this.games[gameType].cdn) {
                                    console.log(`Trying CDN fallback for ${gameType}`);
                                    const fallbackScript = document.createElement('script');
                                    fallbackScript.src = this.games[gameType].cdn;
                                    document.head.appendChild(fallbackScript);
                                    resolve(true);
                                } else {
                                    reject(new Error(`Failed to load ${gameType} script`));
                                }
                            }
                        };
                        
                        document.head.appendChild(script);
                    } else {
                        resolve(true); // Already loaded
                    }
                } catch (error) {
                    if (attempt < retries) {
                        console.warn(`Retry ${attempt}/${retries} for ${gameType}`);
                        setTimeout(() => attemptLoad(attempt + 1), 1000 * attempt);
                    } else {
                        reject(error);
                    }
                }
            };
            
            attemptLoad();
        });
    },
    
    // Preload critical assets for better performance
    preloadCriticalAssets: function() {
        // Preload main CSS and JS
        this.preloadResource(this.global.css.main, 'style');
        this.preloadResource(this.global.js.main, 'script');
        
        // Preload critical game assets
        Object.keys(this.games).forEach(game => {
            if (this.games[game].fallback) {
                this.preloadResource(this.games[game].css, 'style');
                this.preloadResource(this.games[game].js, 'script');
            }
        });
    },
    
    // Helper function to preload resources
    preloadResource: function(url, as) {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.href = this.cache.enabled ? this.cache.getCacheKey(url) : url;
        link.as = as;
        document.head.appendChild(link);
    }
};

// Make it available globally
console.log('StaticPaths configuration loaded for Render');