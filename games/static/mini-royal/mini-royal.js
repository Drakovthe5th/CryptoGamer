class MiniRoyalGame {
    constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.socket = null;
        this.gameId = null;
        this.userId = null;
        this.username = null;
        this.gameState = {
            players: {},
            bullets: [],
            circle_radius: 1.0,
            time_remaining: 90,
            state: 'waiting',
            map: null,
            animation_time: 0
        };
        
        this.animationStates = {
            idle: ["🧍", "🧍", "🧍", "🧍", "🧍", "🧍", "🧍", "🧍"],
            walking: ["🚶", "🚶", "🚶‍➡️", "🚶‍➡️", "🚶", "🚶", "🚶‍⬅️", "🚶‍⬅️"],
            running: ["🏃", "🏃", "🏃‍➡️", "🏃‍➡️", "🏃", "🏃", "🏃‍⬅️", "🏃‍⬅️"],
            shooting: ["🧍", "🧍", "🔫", "🔫", "🧍", "🧍", "🧍", "🧍"],
            dead: ["💀", "💀", "💀", "💀", "💀", "💀", "💀", "💀"]
        };
        
        this.weaponOffsets = {
            pistol: { x: 15, y: -10 },
            knife: { x: 10, y: -5 },
            bow: { x: 20, y: -15 },
            laser: { x: 15, y: -20 }
        };
        
        this.animationFrame = 0;
        this.lastAnimationTime = 0;
        this.animationSpeed = 200;
        this.scale = Math.min(this.canvas.width, this.canvas.height);
        
        this.init();
    }

    init() {
        const urlParams = new URLSearchParams(window.location.search);
        this.gameId = urlParams.get('game_id') || this.generateGameId();
        this.userId = this.getUserId();
        this.username = this.getUsername();
        
        if (!urlParams.get('game_id')) {
            window.history.replaceState({}, '', `${window.location.pathname}?game_id=${this.gameId}`);
        }

        this.connectWebSocket();
        this.setupEventListeners();
        this.resizeCanvas();
        
        this.render();
    }

    generateGameId() {
        return 'game_' + Math.random().toString(36).substr(2, 9);
    }

    getUserId() {
        return Math.floor(Math.random() * 1000000).toString();
    }
    
    getUsername() {
        return 'Player_' + Math.floor(Math.random() * 1000);
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/mini-royal/${this.gameId}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            this.socket.send(JSON.stringify({
                type: 'join',
                user_id: this.userId,
                username: this.username,
                game_id: this.gameId
            }));
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.socket.onclose = () => {
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
                this.gameState.map = data.map;
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
                break;
        }
    }

    setupEventListeners() {
        const shootBtn = document.getElementById('shoot-btn');
        shootBtn.addEventListener('click', () => {
            const centerX = 0.5;
            const centerY = 0.5;
            const player = this.gameState.players[this.userId];
            if (!player) return;
            
            const dx = centerX - player.position[0];
            const dy = centerY - player.position[1];
            const direction = Math.atan2(dy, dx);
            
            this.socket.send(JSON.stringify({
                type: 'shoot',
                direction: direction
            }));
        });

        const startBtn = document.getElementById('start-btn');
        startBtn.addEventListener('click', () => {
            this.socket.send(JSON.stringify({ type: 'start_game' }));
        });

        const playAgainBtn = document.getElementById('play-again');
        playAgainBtn.addEventListener('click', () => {
            window.location.reload();
        });

        const backToLobbyBtn = document.getElementById('back-to-lobby');
        backToLobbyBtn.addEventListener('click', () => {
            window.location.href = '/games';
        });

        window.addEventListener('resize', () => {
            this.resizeCanvas();
        });
    }

    resizeCanvas() {
        const container = this.canvas.parentElement;
        const size = Math.min(container.clientWidth, container.clientHeight) * 0.9;
        
        this.canvas.width = size;
        this.canvas.height = size;
        this.scale = size;
    }

    render() {
        requestAnimationFrame(() => this.render());
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.drawBackground();
        this.drawSafeZone();
        this.drawPlayers();
        this.drawBullets();
        this.drawUI();
    }

    drawBackground() {
        if (!this.gameState.map) {
            this.ctx.fillStyle = '#000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }
        
        this.ctx.fillStyle = this.gameState.map.backgroundColor;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (this.gameState.map.features.includes('grid')) {
            this.drawGrid();
        }
        
        if (this.gameState.map.features.includes('dunes')) {
            this.drawDunes();
        }
        
        if (this.gameState.map.features.includes('snowflakes')) {
            this.drawSnowflakes();
        }
        
        if (this.gameState.map.features.includes('ice_cracks')) {
            this.drawIceCracks();
        }
    }
    
    drawGrid() {
        const size = 20;
        this.ctx.strokeStyle = 'rgba(255, 255, 0, 0.1)';
        this.ctx.lineWidth = 1;
        
        for (let x = 0; x <= this.canvas.width; x += size) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.canvas.height);
            this.ctx.stroke();
        }
        
        for (let y = 0; y <= this.canvas.height; y += size) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();
        }
    }
    
    drawDunes() {
        this.ctx.fillStyle = '#D2B48C';
        for (let i = 0; i < 15; i++) {
            const x = Math.random() * this.canvas.width;
            const y = Math.random() * this.canvas.height;
            const width = 30 + Math.random() * 40;
            const height = 10 + Math.random() * 15;
            
            this.ctx.beginPath();
            this.ctx.moveTo(x, y);
            this.ctx.quadraticCurveTo(x + width/2, y - height, x + width, y);
            this.ctx.fill();
        }
    }
    
    drawSnowflakes() {
        this.ctx.fillStyle = '#FFFFFF';
        const time = Date.now() / 1000;
        
        for (let i = 0; i < 50; i++) {
            const x = (Math.sin(time + i) * 0.5 + 0.5) * this.canvas.width;
            const y = (i/50 + time * 0.1) % 1 * this.canvas.height;
            const size = 2 + Math.sin(time + i) * 1;
            
            this.ctx.beginPath();
            this.ctx.arc(x, y, size, 0, Math.PI * 2);
            this.ctx.fill();
        }
    }
    
    drawIceCracks() {
        this.ctx.strokeStyle = 'rgba(173, 216, 230, 0.6)';
        this.ctx.lineWidth = 1;
        
        for (let i = 0; i < 8; i++) {
            const startX = Math.random() * this.canvas.width;
            const startY = Math.random() * this.canvas.height;
            
            this.ctx.beginPath();
            this.ctx.moveTo(startX, startY);
            
            let currentX = startX;
            let currentY = startY;
            const segments = 5 + Math.floor(Math.random() * 5);
            
            for (let s = 0; s < segments; s++) {
                const angle = Math.random() * Math.PI * 2;
                const length = 20 + Math.random() * 30;
                
                currentX += Math.cos(angle) * length;
                currentY += Math.sin(angle) * length;
                
                currentX = Math.max(0, Math.min(this.canvas.width, currentX));
                currentY = Math.max(0, Math.min(this.canvas.height, currentY));
                
                this.ctx.lineTo(currentX, currentY);
            }
            
            this.ctx.stroke();
        }
    }

    drawSafeZone() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const radius = this.gameState.circle_radius * this.scale / 2;
        
        if (!this.gameState.map) return;
        
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        this.ctx.strokeStyle = this.gameState.map.safeZoneColor;
        this.ctx.lineWidth = 3;
        this.ctx.stroke();
        
        this.ctx.fillStyle = this.gameState.map.safeZoneColor.replace(')', ', 0.1)').replace('rgb', 'rgba');
        this.ctx.globalAlpha = 0.1;
        this.ctx.fill();
        this.ctx.globalAlpha = 1.0;
        
        this.drawDangerZone(centerX, centerY, radius);
    }
    
    drawDangerZone(centerX, centerY, safeRadius) {
        if (!this.gameState.map) return;
        
        const maxRadius = Math.max(this.canvas.width, this.canvas.height);
        const gradient = this.ctx.createRadialGradient(
            centerX, centerY, safeRadius,
            centerX, centerY, maxRadius
        );
        gradient.addColorStop(0, 'transparent');
        gradient.addColorStop(0.5, this.gameState.map.dangerZoneColor);
        gradient.addColorStop(1, this.gameState.map.dangerZoneColor);
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        const pulse = Math.sin(Date.now() / 500) * 0.2 + 0.8;
        this.ctx.globalAlpha = 0.3 * pulse;
        this.ctx.fillStyle = this.gameState.map.dangerZoneColor.replace('0.4', '0.6');
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.globalAlpha = 1.0;
    }

    drawPlayers() {
        for (const userId in this.gameState.players) {
            const player = this.gameState.players[userId];
            if (!player.alive) continue;
            
            const x = player.position[0] * this.canvas.width;
            const y = player.position[1] * this.canvas.height;
            const size = this.scale * 0.05;
            const isCurrentPlayer = userId === this.userId;
            
            this.drawCharacter(x, y, size, player, isCurrentPlayer);
        }
    }
    
    drawCharacter(x, y, size, player, isCurrentPlayer) {
        const state = player.state || 'idle';
        const frame = player.animation_frame || 0;
        
        let emoji;
        if (this.animationStates[state]) {
            emoji = this.animationStates[state][frame % 8];
        } else {
            emoji = player.skin || '🧍';
        }
        
        this.ctx.font = `${size}px Arial`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        
        if (isCurrentPlayer) {
            this.ctx.shadowBlur = 10;
            this.ctx.shadowColor = '#ff0';
        }
        
        this.ctx.fillText(emoji, x, y);
        
        if (isCurrentPlayer) {
            this.ctx.shadowBlur = 0;
        }
        
        if (player.weapon) {
            this.drawWeapon(x, y, size, player.weapon, state, frame);
        }
        
        this.ctx.fillStyle = '#fff';
        this.ctx.font = '12px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(player.username || 'Player', x, y - size - 5);
    }
    
    drawWeapon(x, y, size, weapon, state, frame) {
        const weaponEmojis = {
            pistol: "🔫",
            knife: "🔪",
            bow: "🏹",
            laser: "⚡"
        };
        
        const emoji = weaponEmojis[weapon] || "🔫";
        const offset = this.weaponOffsets[weapon] || { x: 15, y: -10 };
        
        const frameOffset = {
            x: offset.x + (Math.sin(frame * 0.5) * 2),
            y: offset.y + (Math.cos(frame * 0.5) * 2)
        };
        
        this.ctx.font = `${size * 0.6}px Arial`;
        this.ctx.fillText(emoji, x + frameOffset.x, y + frameOffset.y);
    }

    drawBullets() {
        for (const bullet of this.gameState.bullets) {
            const x = bullet.position[0] * this.canvas.width;
            const y = bullet.position[1] * this.canvas.height;
            const size = this.scale * 0.01;
            
            this.ctx.beginPath();
            this.ctx.arc(x, y, size, 0, Math.PI * 2);
            this.ctx.fillStyle = '#ff0';
            this.ctx.fill();
            
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
        const timeEl = document.getElementById('time-remaining');
        if (timeEl) {
            timeEl.textContent = Math.ceil(this.gameState.time_remaining || 0);
        }
        
        const circleProgress = document.querySelector('.circle-progress');
        if (circleProgress && this.gameState.time_remaining) {
            const percentage = (this.gameState.time_remaining / 90) * 100;
            circleProgress.style.background = `conic-gradient(#ff0 ${percentage}%, transparent ${percentage}%)`;
        }
        
        this.updatePlayerCount();
    }

    updatePlayerCount() {
        const aliveCount = Object.values(this.gameState.players).filter(p => p.alive).length;
        const totalCount = Object.keys(this.gameState.players).length;
        
        document.getElementById('alive-count').textContent = aliveCount;
        document.getElementById('total-count').textContent = totalCount;
    }

    showCountdown(value) {
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
            setTimeout(() => countdownEl.remove(), 1000);
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
        if (userId === this.userId) {
            alert('You were eliminated! ' + (reason === 'zone' ? 'You left the safe zone.' : 'You were shot.'));
        }
        this.removePlayer(userId);
    }

    startGame() {
        document.getElementById('lobby').classList.add('hidden');
        document.getElementById('game-ui').classList.remove('hidden');
        this.gameState.state = 'active';
    }

    endGame(winnerId, players) {
        this.gameState.state = 'ended';
        
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
        
        const playerStats = players[this.userId];
        if (playerStats) {
            document.getElementById('kills-stat').textContent = playerStats.kills || 0;
            
            const playerIds = Object.keys(players);
            const sortedPlayers = playerIds.sort((a, b) => {
                if (players[a].alive && !players[b].alive) return -1;
                if (!players[a].alive && players[b].alive) return 1;
                return (players[b].kills || 0) - (players[a].kills || 0);
            });
            
            const position = sortedPlayers.indexOf(this.userId) + 1;
            document.getElementById('position-stat').textContent = `${position}${this.getOrdinalSuffix(position)}`;
        }
    }

    getOrdinalSuffix(i) {
        const j = i % 10;
        const k = i % 100;
        
        if (j === 1 && k !== 11) return 'st';
        if (j === 2 && k !== 12) return 'nd';
        if (j === 3 && k !== 13) return 'rd';
        return 'th';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.miniRoyalGame = new MiniRoyalGame();
});

document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.miniRoyalGame) {
        window.miniRoyalGame.socket.send(JSON.stringify({ type: 'pause' }));
    }
});