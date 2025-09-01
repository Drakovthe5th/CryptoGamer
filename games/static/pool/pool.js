class PoolGame {
    constructor() {
        this.gameState = {
            players: [],
            currentTurn: null,
            pot: 0,
            balls: [],
            status: 'lobby'
        };
        
        this.playerId = null;
        this.gameId = null;
        this.socket = null;
        this.isAiming = false;
        this.currentPower = 0;
        
        this.init();
    }
    
    init() {
        this.initializeTelegramWebApp();
        this.setupEventListeners();
        this.showScreen('lobby-screen');
        this.updateStarsBalance();
    }
    
    initializeTelegramWebApp() {
        // Initialize Telegram WebApp
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
        
        // Get user data from Telegram
        const user = Telegram.WebApp.initDataUnsafe.user;
        if (user) {
            this.playerId = user.id.toString();
            this.playerName = user.first_name || 'Player';
        } else {
            // Fallback for development
            this.playerId = 'dev_' + Math.random().toString(36).substr(2, 9);
            this.playerName = 'Developer';
        }
        
        console.log('Player initialized:', this.playerId, this.playerName);
    }
    
    setupEventListeners() {
        // Game control buttons
        document.getElementById('take-shot-btn').addEventListener('click', () => this.takeShot());
        document.getElementById('forfeit-btn').addEventListener('click', () => this.forfeitGame());
        document.getElementById('chat-btn').addEventListener('click', () => this.openChat());
        
        // Bet amount input
        document.getElementById('bet-amount').addEventListener('input', (e) => {
            const value = Math.max(1, Math.min(100, parseInt(e.target.value) || 1));
            e.target.value = value;
        });
        
        // Game ID input
        document.getElementById('game-id-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.joinGame();
            }
        });
        
        // Chat input
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendChatMessage();
            }
        });
    }
    
    connectWebSocket() {
        // Create WebSocket connection with authentication
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/pool?user_id=${this.playerId}&hash=${this.generateAuthHash()}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.hideError();
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket disconnected');
            this.showError('Connection lost. Reconnecting...');
            
            // Try to reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showError('Connection error');
        };
    }
    
    generateAuthHash() {
        // Simplified auth hash - in production, use proper Telegram WebApp validation
        return btoa(this.playerId + ':' + Date.now()).slice(0, 20);
    }
    
    handleWebSocketMessage(data) {
        if (data.error) {
            this.showError(data.error);
            return;
        }
        
        if (data.action === 'player_joined') {
            this.updateWaitingScreen(data.game_state);
        } else if (data.action === 'game_started') {
            this.startGame(data.game_state);
        } else if (data.action === 'game_state_update') {
            this.updateGameState(data.game_state, data.shot_result);
        } else if (data.action === 'player_forfeited') {
            this.showGameOver(data.winner, true);
        } else if (data.action === 'game_state') {
            this.updateGameState(data.game_state);
        }
    }
    
    createGame() {
        const betAmount = parseInt(document.getElementById('bet-amount').value);
        
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.connectWebSocket();
            
            // Wait for connection before creating game
            setTimeout(() => this.createGame(), 1000);
            return;
        }
        
        this.socket.send(JSON.stringify({
            action: 'create_game',
            bet_amount: betAmount
        }));
    }
    
    joinGame() {
        const gameId = document.getElementById('game-id-input').value.trim();
        
        if (!gameId) {
            this.showError('Please enter a game ID');
            return;
        }
        
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.connectWebSocket();
            
            // Wait for connection before joining game
            setTimeout(() => this.joinGame(), 1000);
            return;
        }
        
        this.socket.send(JSON.stringify({
            action: 'join_game',
            game_id: gameId
        }));
        
        this.hideJoinDialog();
    }
    
    startGame() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.showError('Not connected to server');
            return;
        }
        
        this.socket.send(JSON.stringify({
            action: 'start_game',
            game_id: this.gameId
        }));
    }
    
    takeShot() {
        if (!this.isAiming || this.currentPower < 0.1) {
            return;
        }
        
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.showError('Not connected to server');
            return;
        }
        
        this.socket.send(JSON.stringify({
            action: 'take_shot',
            shot_data: {
                angle: this.gameState.cueAngle || 0,
                power: this.currentPower
            }
        }));
        
        this.isAiming = false;
        this.currentPower = 0;
        this.updatePowerMeter(0);
    }
    
    forfeitGame() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.showError('Not connected to server');
            return;
        }
        
        if (confirm('Are you sure you want to forfeit the game?')) {
            this.socket.send(JSON.stringify({
                action: 'forfeit'
            }));
        }
    }
    
    leaveGame() {
        if (this.socket) {
            this.socket.close();
        }
        
        this.gameId = null;
        this.gameState = {
            players: [],
            currentTurn: null,
            pot: 0,
            balls: [],
            status: 'lobby'
        };
        
        this.showScreen('lobby-screen');
        this.updateStarsBalance();
    }
    
    updateGameState(gameState, shotResult = null) {
        this.gameState = gameState;
        
        // Update UI elements
        this.updatePlayersDisplay();
        this.updatePotDisplay();
        this.updateTurnDisplay();
        this.updateBallsPosition();
        
        // Animate shot result if available
        if (shotResult) {
            this.animateShotResult(shotResult);
        }
        
        // Enable/disable shot button based on turn
        const isMyTurn = this.gameState.currentTurn === this.playerId;
        document.getElementById('take-shot-btn').disabled = !isMyTurn;
        
        // Setup aiming if it's player's turn
        if (isMyTurn) {
            this.setupAiming();
        }
    }
    
    setupAiming() {
        const table = document.querySelector('.pool-table-container');
        const powerLevel = document.getElementById('power-level');
        const powerPercent = document.getElementById('power-percent');
        
        const handleStart = (x, y) => {
            this.isAiming = true;
            this.currentPower = 0;
            this.updatePowerMeter(0);
        };
        
        const handleMove = (x, y) => {
            if (!this.isAiming) return;
            
            // Calculate power based on distance (simplified)
            const rect = table.getBoundingClientRect();
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const distance = Math.sqrt(
                Math.pow(x - centerX, 2) + 
                Math.pow(y - centerY, 2)
            );
            
            this.currentPower = Math.min(distance / 100, 1);
            this.updatePowerMeter(this.currentPower);
            
            // Update cue angle
            const cueBall = this.gameState.balls.find(b => b.type === 'cue');
            if (cueBall) {
                const angle = Math.atan2(y - cueBall.y, x - cueBall.x);
                this.gameState.cueAngle = angle;
                this.updateCueStick(angle);
            }
        };
        
        const handleEnd = () => {
            if (this.isAiming && this.currentPower > 0.1) {
                this.takeShot();
            }
            this.isAiming = false;
        };
        
        // Mouse events
        table.addEventListener('mousedown', (e) => {
            handleStart(e.clientX, e.clientY);
        });
        
        table.addEventListener('mousemove', (e) => {
            handleMove(e.clientX, e.clientY);
        });
        
        table.addEventListener('mouseup', handleEnd);
        
        // Touch events
        table.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            handleStart(touch.clientX, touch.clientY);
        });
        
        table.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            handleMove(touch.clientX, touch.clientY);
        });
        
        table.addEventListener('touchend', handleEnd);
    }
    
    updatePowerMeter(power) {
        const powerLevel = document.getElementById('power-level');
        const powerPercent = document.getElementById('power-percent');
        
        powerLevel.style.width = `${power * 100}%`;
        powerPercent.textContent = `${Math.round(power * 100)}%`;
    }
    
    updateCueStick(angle) {
        const cueStick = document.getElementById('cue-stick');
        const cueBall = this.gameState.balls.find(b => b.type === 'cue');
        
        if (cueBall && cueStick) {
            const x = cueBall.x - 20 * Math.cos(angle);
            const y = cueBall.y - 20 * Math.sin(angle);
            
            cueStick.style.left = `${x - 150}px`;
            cueStick.style.top = `${y - 5}px`;
            cueStick.style.transform = `rotate(${angle}rad)`;
            cueStick.style.display = 'block';
        }
    }
    
    updateBallsPosition() {
        const ballsContainer = document.getElementById('balls-container');
        ballsContainer.innerHTML = '';
        
        this.gameState.balls.forEach(ball => {
            if (!ball.potted) {
                const ballElement = document.createElement('div');
                ballElement.className = 'pool-ball';
                ballElement.style.left = `${ball.x - 16}px`;
                ballElement.style.top = `${ball.y - 16}px`;
                
                if (ball.type === 'cue') {
                    ballElement.style.backgroundImage = 'url(assets/images/ball-cue.png)';
                } else {
                    ballElement.style.backgroundImage = `url(assets/images/ball-${ball.number}.png)`;
                }
                
                ballsContainer.appendChild(ballElement);
            }
        });
        
        // Update cue stick position
        if (this.gameState.currentTurn === this.playerId) {
            const cueBall = this.gameState.balls.find(b => b.type === 'cue');
            if (cueBall) {
                this.updateCueStick(this.gameState.cueAngle || 0);
            }
        } else {
            document.getElementById('cue-stick').style.display = 'none';
        }
    }
    
    animateShotResult(shotResult) {
        // Simple animation for shot result
        if (shotResult.ball_potted) {
            // Add particle effect for potted ball
            this.createParticleEffect();
        }
    }

    createParticleEffect() {
        // Simple particle effect for visual feedback
        const table = document.querySelector('.pool-table-container');
        const particles = document.createElement('div');
        particles.className = 'particle-effect';
        particles.style.position = 'absolute';
        particles.style.top = '50%';
        particles.style.left = '50%';
        particles.style.transform = 'translate(-50%, -50%)';
        particles.style.zIndex = '8';
        particles.style.pointerEvents = 'none';
        
        for (let i = 0; i < 15; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.position = 'absolute';
            particle.style.width = '8px';
            particle.style.height = '8px';
            particle.style.background = '#ffcc00';
            particle.style.borderRadius = '50%';
            particle.style.opacity = '0';
            
            // Random direction and distance
            const angle = Math.random() * Math.PI * 2;
            const distance = 30 + Math.random() * 70;
            const duration = 0.5 + Math.random() * 0.5;
            
            particle.style.animation = `
                particleMove ${duration}s ease-out forwards,
                particleFade ${duration}s ease-out forwards
            `;
            
            particle.style.setProperty('--angle', angle);
            particle.style.setProperty('--distance', distance + 'px');
            
            particles.appendChild(particle);
        }
        
        table.appendChild(particles);
        
        // Remove particles after animation
        setTimeout(() => {
            table.removeChild(particles);
        }, 1000);
    }

    updatePlayersDisplay() {
        const playersDisplay = document.getElementById('players-display');
        playersDisplay.innerHTML = '';
        
        this.gameState.players.forEach(playerId => {
            const isCurrentPlayer = this.gameState.currentTurn === playerId;
            const isMe = playerId === this.playerId;
            
            const playerElement = document.createElement('div');
            playerElement.className = `player-display ${isCurrentPlayer ? 'current-player' : ''}`;
            
            const avatar = document.createElement('div');
            avatar.className = 'player-avatar';
            avatar.textContent = isMe ? 'YOU' : playerId.charAt(0).toUpperCase();
            
            const name = document.createElement('div');
            name.className = 'player-name';
            name.textContent = isMe ? 'You' : `Player ${playerId.substr(0, 4)}`;
            
            const bet = document.createElement('div');
            bet.className = 'player-bet';
            bet.textContent = this.gameState.bets && this.gameState.bets[playerId] 
                ? `${this.gameState.bets[playerId]}⭐` 
                : '0⭐';
            
            playerElement.appendChild(avatar);
            playerElement.appendChild(name);
            playerElement.appendChild(bet);
            
            playersDisplay.appendChild(playerElement);
        });
    }

    updatePotDisplay() {
        const potAmount = document.getElementById('pot-amount');
        potAmount.textContent = this.gameState.pot || '0';
    }

    updateTurnDisplay() {
        const turnDisplay = document.getElementById('turn-display');
        
        if (this.gameState.currentTurn === this.playerId) {
            turnDisplay.textContent = 'Your turn! Aim and shoot.';
            turnDisplay.style.color = '#ffcc00';
        } else if (this.gameState.currentTurn) {
            turnDisplay.textContent = `${this.gameState.currentTurn}'s turn...`;
            turnDisplay.style.color = '#ccc';
        } else {
            turnDisplay.textContent = 'Waiting for game to start...';
            turnDisplay.style.color = '#ccc';
        }
    }

    updateWaitingScreen(gameState) {
        this.gameState = gameState;
        this.gameId = gameState.game_id;
        
        // Update waiting screen info
        document.getElementById('waiting-game-id').textContent = this.gameId;
        document.getElementById('waiting-bet-amount').textContent = gameState.required_bet || gameState.bet_amount;
        document.getElementById('waiting-pot').textContent = gameState.pot;
        
        // Update players list
        const playersList = document.getElementById('waiting-players-list');
        playersList.innerHTML = '';
        
        gameState.players.forEach(playerId => {
            const playerElement = document.createElement('div');
            playerElement.className = 'player-badge';
            playerElement.textContent = playerId === this.playerId ? 'You' : `Player ${playerId.substr(0, 4)}`;
            playersList.appendChild(playerElement);
        });
        
        // Enable start button if user is the first player (game creator)
        const startButton = document.querySelector('.start-game');
        if (gameState.players.length >= 2 && gameState.players[0] === this.playerId) {
            startButton.disabled = false;
        } else {
            startButton.disabled = true;
        }
        
        this.showScreen('waiting-screen');
    }

    startGame(gameState) {
        this.gameState = gameState;
        this.showScreen('game-screen');
        this.updateGameState(gameState);
        
        // Setup aiming for the first turn
        if (this.gameState.currentTurn === this.playerId) {
            this.setupAiming();
        }
    }

    showGameOver(winner, isForfeit = false) {
        const winnerDisplay = document.getElementById('winner-display');
        const finalPot = document.getElementById('final-pot');
        
        if (winner === this.playerId) {
            winnerDisplay.textContent = 'You won!';
            winnerDisplay.style.color = '#ffcc00';
        } else {
            winnerDisplay.textContent = `${winner} won!`;
            winnerDisplay.style.color = '#ff6b00';
        }
        
        finalPot.textContent = this.gameState.pot;
        
        this.showScreen('game-over-screen');
    }

    showScreen(screenId) {
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        
        // Show the requested screen
        document.getElementById(screenId).classList.add('active');
    }

    showJoinDialog() {
        document.getElementById('join-screen').classList.add('active');
    }

    hideJoinDialog() {
        document.getElementById('join-screen').classList.remove('active');
    }

    openChat() {
        document.getElementById('chat-overlay').style.display = 'flex';
    }

    closeChat() {
        document.getElementById('chat-overlay').style.display = 'none';
    }

    sendChatMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        
        if (message && this.socket && this.socket.readyState === WebSocket.OPEN) {
            // In a real implementation, you would send chat messages via WebSocket
            this.addChatMessage(this.playerName, message);
            chatInput.value = '';
        }
    }

    addChatMessage(sender, message) {
        const chatMessages = document.getElementById('chat-messages');
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message';
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message}`;
        
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    showError(message) {
        const errorDisplay = document.getElementById('error-display');
        errorDisplay.textContent = message;
        errorDisplay.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.hideError();
        }, 5000);
    }

    hideError() {
        document.getElementById('error-display').style.display = 'none';
    }

    updateStarsBalance() {
        // This would typically fetch from your backend
        // For now, we'll use a placeholder
        document.getElementById('stars-balance').textContent = '100';
    }

    // UI helper functions
    function toggleMenu() {
        const menu = document.getElementById('menu-overlay');
        menu.style.display = menu.style.display === 'flex' ? 'none' : 'flex';
    }

    // Global functions for HTML onclick handlers
    window.createGame = function() {
        window.poolGame.createGame();
    };

    window.joinGame = function() {
        window.poolGame.joinGame();
    };

    window.startGame = function() {
        window.poolGame.startGame();
    };

    window.leaveGame = function() {
        window.poolGame.leaveGame();
    };

    window.showJoinDialog = function() {
        window.poolGame.showJoinDialog();
    };

    window.hideJoinDialog = function() {
        window.poolGame.hideJoinDialog();
    };

    window.returnToLobby = function() {
        window.poolGame.leaveGame();
    };

    window.sendChatMessage = function() {
        window.poolGame.sendChatMessage();
    };

    window.closeChat = function() {
        window.poolGame.closeChat();
    };

    // Initialize the game when the page loads
    document.addEventListener('DOMContentLoaded', () => {
        window.poolGame = new PoolGame();
        
        // Add CSS for particle animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes particleMove {
                from {
                    transform: translate(0, 0);
                }
                to {
                    transform: translate(
                        calc(cos(var(--angle)) * var(--distance)),
                        calc(sin(var(--angle)) * var(--distance))
                    );
                }
            }
            
            @keyframes particleFade {
                0% {
                    opacity: 0;
                    transform: scale(0.5);
                }
                50% {
                    opacity: 1;
                    transform: scale(1.2);
                }
                100% {
                    opacity: 0;
                    transform: scale(0.8);
                }
            }
            
            .particle {
                will-change: transform, opacity;
            }
        `;
        document.head.appendChild(style);
});