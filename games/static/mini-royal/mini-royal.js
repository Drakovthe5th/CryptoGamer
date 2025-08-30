class MiniRoyalGame {
    constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.socket = null;
        this.gameId = null;
        this.userId = null;
        this.gameState = {
            players: {},
            bullets: [],
            circleRadius: 1.0,
            timeRemaining: 90,
            state: 'waiting' // waiting, countdown, active, ended
        };
        this.playerSkins = {};
        this.animationFrame = null;
        this.scale = Math.min(this.canvas.width, this.canvas.height);
        
        this.init();
    }

    init() {
        // Get game ID from URL or generate a new one
        const urlParams = new URLSearchParams(window.location.search);
        this.gameId = urlParams.get('game_id') || this.generateGameId();
        this.userId = this.getUserId(); // This would come from your auth system
        
        // Update URL with game ID
        if (!urlParams.get('game_id')) {
            window.history.replaceState({}, '', `${window.location.pathname}?game_id=${this.gameId}`);
        }

        this.connectWebSocket();
        this.setupEventListeners();
        this.resizeCanvas();
        
        // Start the animation loop
        this.render();
    }

    generateGameId() {
        return 'game_' + Math.random().toString(36).substr(2, 9);
    }

    getUserId() {
        // This should be replaced with your actual user ID retrieval logic
        return Math.floor(Math.random() * 1000000).toString();
    }

    connectWebSocket() {
        // Connect to the WebSocket endpoint
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/mini-royal/${this.gameId}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('Connected to Mini Royal server');
            // Send join message
            this.socket.send(JSON.stringify({
                type: 'join',
                user_id: this.userId,
                game_id: this.gameId
            }));
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.socket.onclose = () => {
            console.log('Disconnected from Mini Royal server');
            // Try to reconnect after a delay
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'game_state':
                this.gameState = data;
                this.updatePlayerCount();
                break;
                
            case 'countdown':
                this.showCountdown(data.value);
                break;
                
            case 'player_joined':
                this.addPlayer(data.player);
                break;
                
            case 'player_left':
                this.removePlayer(data.user_id);
                break;
                
            case 'player_eliminated':
                this.handlePlayerEliminated(data.user_id, data.reason, data.killer_id);
                break;
                
            case 'game_start':
                this.startGame();
                break;
                
            case 'game_end':
                this.endGame(data.winner_id, data.players);
                break;
                
            case 'error':
                console.error('Game error:', data.message);
                alert(data.message);
                break;
        }
    }

    setupEventListeners() {
        // Shoot button
        const shootBtn = document.getElementById('shoot-btn');
        shootBtn.addEventListener('click', () => {
            // Calculate direction toward center for simplicity
            // In a real game, you might implement aiming
            const centerX = 0.5;
            const centerY = 0.5;
            const dx = centerX - this.gameState.players[this.userId].position[0];
            const dy = centerY - this.gameState.players[this.userId].position[1];
            const direction = Math.atan2(dy, dx);
            
            this.socket.send(JSON.stringify({
                type: 'shoot',
                direction: direction
            }));
        });

        // Start game button (for the host)
        const startBtn = document.getElementById('start-btn');
        startBtn.addEventListener('click', () => {
            this.socket.send(JSON.stringify({
                type: 'start_game'
            }));
        });

        // Play again button
        const playAgainBtn = document.getElementById('play-again');
        playAgainBtn.addEventListener('click', () => {
            window.location.reload();
        });

        // Back to lobby button
        const backToLobbyBtn = document.getElementById('back-to-lobby');
        backToLobbyBtn.addEventListener('click', () => {
            window.location.href = '/games'; // Adjust to your games page URL
        });

        // Window resize
        window.addEventListener('resize', () => {
            this.resizeCanvas();
        });
    }

    resizeCanvas() {
        // Make canvas responsive
        const container = this.canvas.parentElement;
        const size = Math.min(container.clientWidth, container.clientHeight) * 0.9;
        
        this.canvas.width = size;
        this.canvas.height = size;
        this.scale = size;
    }

    render() {
        this.animationFrame = requestAnimationFrame(() => this.render());
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw background
        this.drawBackground();
        
        // Draw safe circle
        this.drawSafeCircle();
        
        // Draw players
        this.drawPlayers();
        
        // Draw bullets
        this.drawBullets();
        
        // Draw UI elements
        this.drawUI();
    }

    drawBackground() {
        // Draw black background
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Add some subtle glowing effects
        const gradient = this.ctx.createRadialGradient(
            this.canvas.width / 2,
            this.canvas.height / 2,
            0,
            this.canvas.width / 2,
            this.canvas.height / 2,
            this.canvas.width / 2
        );
        
        gradient.addColorStop(0, 'rgba(255, 255, 0, 0.1)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    drawSafeCircle() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const radius = this.gameState.circleRadius * this.scale / 2;
        
        // Draw safe circle
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = '#0f0';
        this.ctx.lineWidth = 3;
        this.ctx.stroke();
        
        // Draw danger zone (outside circle)
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';
        this.ctx.fill();
    }

    drawPlayers() {
        for (const userId in this.gameState.players) {
            if (!this.gameState.players[userId].alive) continue;
            
            const player = this.gameState.players[userId];
            const x = player.position[0] * this.scale;
            const y = player.position[1] * this.scale;
            const radius = this.scale * 0.02;
            
            // Draw player circle
            this.ctx.beginPath();
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            
            // Use yellow for current player, red for others
            if (userId === this.userId) {
                this.ctx.fillStyle = '#ff0'; // Yellow for current player
            } else {
                this.ctx.fillStyle = '#f00'; // Red for other players
            }
            
            this.ctx.fill();
            
            // Draw player direction indicator
            const directionX = x + Math.cos(player.direction || 0) * radius * 1.5;
            const directionY = y + Math.sin(player.direction || 0) * radius * 1.5;
            
            this.ctx.beginPath();
            this.ctx.moveTo(x, y);
            this.ctx.lineTo(directionX, directionY);
            this.ctx.strokeStyle = '#fff';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            
            // Draw player name
            this.ctx.fillStyle = '#fff';
            this.ctx.font = '12px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(player.username || 'Player', x, y - radius - 5);
        }
    }

    drawBullets() {
        for (const bullet of this.gameState.bullets) {
            const x = bullet.position[0] * this.scale;
            const y = bullet.position[1] * this.scale;
            const radius = this.scale * 0.01;
            
            // Draw bullet
            this.ctx.beginPath();
            this.ctx.arc(x, y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = '#ff0';
            this.ctx.fill();
            
            // Draw bullet trail
            const trailLength = 10;
            const trailX = x - Math.cos(bullet.direction) * trailLength;
            const trailY = y - Math.sin(bullet.direction) * trailLength;
            
            this.ctx.beginPath();
            this.ctx.moveTo(trailX, trailY);
            this.ctx.lineTo(x, y);
            this.ctx.strokeStyle = 'rgba(255, 255, 0, 0.5)';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
        }
    }

    drawUI() {
        // Draw time remaining
        const timeEl = document.getElementById('time-remaining');
        if (timeEl) {
            timeEl.textContent = Math.ceil(this.gameState.timeRemaining);
        }
        
        // Draw circle timer animation
        const circleProgress = document.querySelector('.circle-progress');
        if (circleProgress) {
            const percentage = (this.gameState.timeRemaining / 90) * 100;
            circleProgress.style.background = `conic-gradient(#ff0 ${percentage}%, transparent ${percentage}%)`;
        }
    }

    updatePlayerCount() {
        const aliveCount = Object.values(this.gameState.players).filter(p => p.alive).length;
        const totalCount = Object.keys(this.gameState.players).length;
        
        document.getElementById('alive-count').textContent = aliveCount;
        document.getElementById('total-count').textContent = totalCount;
    }

    showCountdown(value) {
        // Create or update countdown display
        let countdownEl = document.getElementById('countdown');
        if (!countdownEl) {
            countdownEl = document.createElement('div');
            countdownEl.id = 'countdown';
            countdownEl.style.position = 'absolute';
            countdownEl.style.top = '50%';
            countdownEl.style.left = '50%';
            countdownEl.style.transform = 'translate(-50%, -50%)';
            countdownEl.style.fontSize = '100px';
            countdownEl.style.color = '#ff0';
            countdownEl.style.zIndex = '100';
            document.querySelector('.game-container').appendChild(countdownEl);
        }
        
        countdownEl.textContent = value;
        
        if (value === 0) {
            setTimeout(() => {
                countdownEl.remove();
            }, 1000);
        }
    }

    addPlayer(player) {
        this.gameState.players[player.user_id] = player;
        this.updatePlayerCount();
    }

    removePlayer(userId) {
        delete this.gameState.players[userId];
        this.updatePlayerCount();
    }

    handlePlayerEliminated(userId, reason, killerId) {
        // Visual effect for elimination
        if (userId === this.userId) {
            // Current player was eliminated
            alert('You were eliminated! ' + (reason === 'zone' ? 'You left the safe zone.' : 'You were shot.'));
        }
        
        // Remove player from game
        this.removePlayer(userId);
    }

    startGame() {
        // Hide lobby, show game UI
        document.getElementById('lobby').classList.add('hidden');
        document.getElementById('game-ui').classList.remove('hidden');
        
        this.gameState.state = 'active';
    }

    endGame(winnerId, players) {
        this.gameState.state = 'ended';
        
        // Show game over screen
        const gameOverEl = document.getElementById('game-over');
        gameOverEl.classList.remove('hidden');
        
        const winnerDisplay = document.getElementById('winner-display');
        if (winnerId === this.userId) {
            winnerDisplay.textContent = 'You Won!';
            winnerDisplay.style.color = '#ff0';
        } else {
            const winner = this.gameState.players[winnerId];
            winnerDisplay.textContent = `${winner.username} Won!`;
            winnerDisplay.style.color = '#f00';
        }
        
        // Update stats
        const playerStats = players[this.userId];
        if (playerStats) {
            document.getElementById('kills-stat').textContent = playerStats.kills || 0;
            
            // Calculate position (this would need proper logic from backend)
            const playerIds = Object.keys(players);
            const sortedPlayers = playerIds.sort((a, b) => {
                if (players[a].alive && !players[b].alive) return -1;
                if (!players[a].alive && players[b].alive) return 1;
                return (players[b].kills || 0) - (players[a].kills || 0);
            });
            
            const position = sortedPlayers.indexOf(this.userId) + 1;
            document.getElementById('position-stat').textContent = `${position}${this.getOrdinalSuffix(position)}`;
        }
        
        // Cancel animation frame
        cancelAnimationFrame(this.animationFrame);
    }

    getOrdinalSuffix(i) {
        const j = i % 10;
        const k = i % 100;
        
        if (j === 1 && k !== 11) return 'st';
        if (j === 2 && k !== 12) return 'nd';
        if (j === 3 && k !== 13) return 'rd';
        return 'th';
    }

    sendChatMessage(message) {
        this.socket.send(JSON.stringify({
            type: 'chat',
            message: message
        }));
    }
}

// Initialize game when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.miniRoyalGame = new MiniRoyalGame();
});

// Handle page visibility change
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.miniRoyalGame) {
        // Page is hidden, pause game or notify server
        window.miniRoyalGame.socket.send(JSON.stringify({
            type: 'pause'
        }));
    }
});

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MiniRoyalGame;
}