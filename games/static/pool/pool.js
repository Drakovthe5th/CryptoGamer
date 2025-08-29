class PoolGame {
    constructor() {
        this.gameId = null;
        this.playerId = null;
        this.playerName = null;
        this.websocket = null;
        this.connected = false;
        this.gameState = 'waiting';
        this.players = [];
        this.bets = {};
        this.pot = 0;
        this.currentPlayerIndex = 0;
        this.isMyTurn = false;
        
        // Game elements
        this.tableElement = null;
        this.ballsElement = null;
        this.cueElement = null;
        this.interfaceElement = null;
        
        // Initialize the game
        this.init();
    }
    
    init() {
        // Get player info from Telegram Mini App
        this.playerId = Telegram.WebApp.initDataUnsafe.user?.id || 'guest_' + Math.random().toString(36).substr(2, 9);
        this.playerName = Telegram.WebApp.initDataUnsafe.user?.first_name || 'Player';
        
        // Set up UI event listeners
        this.setupEventListeners();
        
        // Initialize game graphics (simplified for this example)
        this.initGraphics();
        
        // Show main menu
        this.showMainMenu();
    }
    
    setupEventListeners() {
        // Main menu events
        document.getElementById('create-game-btn').addEventListener('click', () => this.createGame());
        document.getElementById('join-game-btn').addEventListener('click', () => this.showJoinGameDialog());
        document.getElementById('join-game-submit').addEventListener('click', () => this.joinGame());
        document.getElementById('game-id-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.joinGame();
        });
        
        // Betting interface events
        document.getElementById('place-bet-btn').addEventListener('click', () => this.placeBet());
        document.getElementById('bet-amount').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.placeBet();
        });
        
        // Game control events
        document.getElementById('leave-game-btn').addEventListener('click', () => this.leaveGame());
        document.getElementById('send-chat-btn').addEventListener('click', () => this.sendChatMessage());
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendChatMessage();
        });
    }
    
    initGraphics() {
        // This is a simplified implementation
        // In a real game, you would use a canvas or WebGL for the pool table
        
        this.tableElement = document.getElementById('pool-table');
        this.ballsElement = document.getElementById('pool-balls');
        this.cueElement = document.getElementById('pool-cue');
        this.interfaceElement = document.getElementById('game-interface');
        
        // Set up mouse/touch controls for aiming and shooting
        this.setupControls();
    }
    
    setupControls() {
        let isDragging = false;
        let startX, startY;
        let power = 0;
        
        this.tableElement.addEventListener('mousedown', (e) => {
            if (!this.isMyTurn) return;
            
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            
            // Show power meter
            document.getElementById('power-meter').style.display = 'block';
        });
        
        this.tableElement.addEventListener('mousemove', (e) => {
            if (!isDragging || !this.isMyTurn) return;
            
            // Calculate angle based on mouse position relative to cue ball
            const rect = this.tableElement.getBoundingClientRect();
            const cueBall = document.getElementById('cue-ball');
            const cueBallRect = cueBall.getBoundingClientRect();
            const cueBallX = cueBallRect.left + cueBallRect.width / 2;
            const cueBallY = cueBallRect.top + cueBallRect.height / 2;
            
            const angle = Math.atan2(e.clientY - cueBallY, e.clientX - cueBallX);
            
            // Update cue position
            this.cueElement.style.transform = `rotate(${angle}rad)`;
            
            // Calculate power based on drag distance
            const distance = Math.sqrt(Math.pow(e.clientX - startX, 2) + Math.pow(e.clientY - startY, 2));
            power = Math.min(distance / 100, 1); // Normalize to 0-1
            
            // Update power meter
            document.getElementById('power-level').style.width = `${power * 100}%`;
        });
        
        this.tableElement.addEventListener('mouseup', (e) => {
            if (!isDragging || !this.isMyTurn) return;
            
            isDragging = false;
            
            // Hide power meter
            document.getElementById('power-meter').style.display = 'none';
            
            // Take shot with calculated angle and power
            const rect = this.tableElement.getBoundingClientRect();
            const cueBall = document.getElementById('cue-ball');
            const cueBallRect = cueBall.getBoundingClientRect();
            const cueBallX = cueBallRect.left + cueBallRect.width / 2;
            const cueBallY = cueBallRect.top + cueBallRect.height / 2;
            
            const angle = Math.atan2(e.clientY - cueBallY, e.clientX - cueBallX);
            
            this.takeShot(angle, power);
        });
        
        // Add touch events for mobile devices
        this.tableElement.addEventListener('touchstart', (e) => {
            if (!this.isMyTurn) return;
            e.preventDefault();
            
            isDragging = true;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            
            document.getElementById('power-meter').style.display = 'block';
        });
        
        this.tableElement.addEventListener('touchmove', (e) => {
            if (!isDragging || !this.isMyTurn) return;
            e.preventDefault();
            
            const rect = this.tableElement.getBoundingClientRect();
            const cueBall = document.getElementById('cue-ball');
            const cueBallRect = cueBall.getBoundingClientRect();
            const cueBallX = cueBallRect.left + cueBallRect.width / 2;
            const cueBallY = cueBallRect.top + cueBallRect.height / 2;
            
            const angle = Math.atan2(e.touches[0].clientY - cueBallY, e.touches[0].clientX - cueBallX);
            this.cueElement.style.transform = `rotate(${angle}rad)`;
            
            const distance = Math.sqrt(Math.pow(e.touches[0].clientX - startX, 2) + Math.pow(e.touches[0].clientY - startY, 2));
            power = Math.min(distance / 100, 1);
            
            document.getElementById('power-level').style.width = `${power * 100}%`;
        });
        
        this.tableElement.addEventListener('touchend', (e) => {
            if (!isDragging || !this.isMyTurn) return;
            
            isDragging = false;
            document.getElementById('power-meter').style.display = 'none';
            
            const rect = this.tableElement.getBoundingClientRect();
            const cueBall = document.getElementById('cue-ball');
            const cueBallRect = cueBall.getBoundingClientRect();
            const cueBallX = cueBallRect.left + cueBallRect.width / 2;
            const cueBallY = cueBallRect.top + cueBallRect.height / 2;
            
            const angle = Math.atan2(e.changedTouches[0].clientY - cueBallY, e.changedTouches[0].clientX - cueBallX);
            this.takeShot(angle, power);
        });
    }
    
    connectWebSocket() {
        // Determine WebSocket URL based on environment
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/pool`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            this.connected = true;
            console.log('WebSocket connected');
        };
        
        this.websocket.onmessage = (event) => {
            this.handleMessage(JSON.parse(event.data));
        };
        
        this.websocket.onclose = () => {
            this.connected = false;
            console.log('WebSocket disconnected');
            this.showError('Connection lost. Trying to reconnect...');
            
            // Try to reconnect after 5 seconds
            setTimeout(() => this.connectWebSocket(), 5000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showError('Connection error');
        };
    }
    
    handleMessage(data) {
        console.log('Received message:', data);
        
        switch(data.action) {
            case 'game_created':
                this.handleGameCreated(data);
                break;
            case 'player_joined':
                this.handlePlayerJoined(data);
                break;
            case 'betting_started':
                this.handleBettingStarted(data);
                break;
            case 'bet_placed':
                this.handleBetPlaced(data);
                break;
            case 'game_started':
                this.handleGameStarted(data);
                break;
            case 'shot_taken':
                this.handleShotTaken(data);
                break;
            case 'game_ended':
                this.handleGameEnded(data);
                break;
            case 'player_left':
                this.handlePlayerLeft(data);
                break;
            case 'chat_message':
                this.handleChatMessage(data);
                break;
            case 'game_status':
                this.handleGameStatus(data);
                break;
            case 'error':
                this.handleError(data);
                break;
        }
    }
    
    sendMessage(data) {
        if (this.connected) {
            this.websocket.send(JSON.stringify(data));
        } else {
            this.showError('Not connected to server');
        }
    }
    
    createGame() {
        if (!this.connected) {
            this.connectWebSocket();
            
            // Wait for connection before creating game
            setTimeout(() => {
                this.sendMessage({
                    action: 'create_game',
                    player_id: this.playerId,
                    player_name: this.playerName,
                    max_players: 2, // Default to 1v1
                    game_type: '1v1'
                });
            }, 1000);
        } else {
            this.sendMessage({
                action: 'create_game',
                player_id: this.playerId,
                player_name: this.playerName,
                max_players: 2,
                game_type: '1v1'
            });
        }
    }
    
    joinGame() {
        const gameId = document.getElementById('game-id-input').value.trim();
        
        if (!gameId) {
            this.showError('Please enter a game ID');
            return;
        }
        
        if (!this.connected) {
            this.connectWebSocket();
            
            // Wait for connection before joining game
            setTimeout(() => {
                this.sendMessage({
                    action: 'join_game',
                    game_id: gameId,
                    player_id: this.playerId,
                    player_name: this.playerName
                });
            }, 1000);
        } else {
            this.sendMessage({
                action: 'join_game',
                game_id: gameId,
                player_id: this.playerId,
                player_name: this.playerName
            });
        }
        
        // Hide join dialog
        this.hideJoinGameDialog();
    }
    
    placeBet() {
        const amount = parseInt(document.getElementById('bet-amount').value);
        
        if (isNaN(amount) || amount <= 0) {
            this.showError('Please enter a valid bet amount');
            return;
        }
        
        this.sendMessage({
            action: 'place_bet',
            game_id: this.gameId,
            player_id: this.playerId,
            amount: amount
        });
    }
    
    takeShot(angle, power) {
        this.sendMessage({
            action: 'take_shot',
            game_id: this.gameId,
            player_id: this.playerId,
            angle: angle,
            power: power
        });
    }
    
    leaveGame() {
        this.sendMessage({
            action: 'leave_game',
            game_id: this.gameId,
            player_id: this.playerId
        });
        
        // Return to main menu
        this.showMainMenu();
    }
    
    sendChatMessage() {
        const message = document.getElementById('chat-input').value.trim();
        
        if (!message) return;
        
        this.sendMessage({
            action: 'chat_message',
            game_id: this.gameId,
            player_id: this.playerId,
            message: message
        });
        
        // Clear input
        document.getElementById('chat-input').value = '';
    }
    
    requestGameStatus() {
        this.sendMessage({
            action: 'get_game_status',
            game_id: this.gameId
        });
    }
    
    startGame() {
        this.sendMessage({
            action: 'start_game',
            game_id: this.gameId,
            player_id: this.playerId
        });
    }
    
    handleGameCreated(data) {
        this.gameId = data.game_id;
        this.showLobby();
        
        // Update UI
        document.getElementById('game-id-display').textContent = data.game_id;
        document.getElementById('game-status').textContent = 'Waiting for players...';
    }
    
    handlePlayerJoined(data) {
        this.players = data.players;
        this.updatePlayersList();
        
        // If I'm the game creator and all players have joined, show start button
        if (this.players.length > 0 && this.players[0].id === this.playerId && this.players.length === this.maxPlayers) {
            document.getElementById('start-game-btn').style.display = 'block';
        }
    }
    
    handleBettingStarted(data) {
        this.gameState = 'betting';
        this.showBettingInterface();
    }
    
    handleBetPlaced(data) {
        this.bets[data.player_id] = data.amount;
        this.pot = data.pot;
        
        this.updateBetsDisplay();
        
        // If it's me who placed the bet, hide betting interface
        if (data.player_id === this.playerId) {
            document.getElementById('betting-interface').style.display = 'none';
        }
    }
    
    handleGameStarted(data) {
        this.gameState = 'playing';
        this.pot = data.pot;
        this.currentPlayerIndex = data.current_player;
        this.isMyTurn = (this.players[this.currentPlayerIndex].id === this.playerId);
        
        this.showGameInterface();
        this.updateGameStatus();
    }
    
    handleShotTaken(data) {
        // Update game state based on shot result
        this.currentPlayerIndex = data.next_player;
        this.isMyTurn = (this.players[this.currentPlayerIndex].id === this.playerId);
        
        // Animate the shot (simplified)
        this.animateShot(data.angle, data.power, data.result);
        
        this.updateGameStatus();
    }
    
    handleGameEnded(data) {
        this.gameState = 'ended';
        
        // Show winner and pot
        const winnerName = this.players.find(p => p.id === data.winner)?.name || 'Unknown';
        
        document.getElementById('game-result').innerHTML = `
            <h2>Game Over!</h2>
            <p>Winner: ${winnerName}</p>
            <p>Pot: ${data.pot} Stars</p>
        `;
        
        document.getElementById('game-result').style.display = 'block';
        
        // Return to main menu after 5 seconds
        setTimeout(() => {
            this.showMainMenu();
        }, 5000);
    }
    
    handlePlayerLeft(data) {
        this.players = data.players;
        this.updatePlayersList();
        
        // If too many players left, end the game
        if (this.players.length < 2 && this.gameState === 'playing') {
            this.showError('Not enough players. Game ending...');
            
            // Return to main menu after 3 seconds
            setTimeout(() => {
                this.showMainMenu();
            }, 3000);
        }
    }
    
    handleChatMessage(data) {
        this.addChatMessage(data.player_id, data.message, data.timestamp);
    }
    
    handleGameStatus(data) {
        // Update game state with received status
        this.gameState = data.status.state;
        this.players = data.status.players;
        this.bets = data.status.bets;
        this.pot = data.status.pot;
        this.currentPlayerIndex = data.status.current_player_index;
        this.isMyTurn = (this.players[this.currentPlayerIndex].id === this.playerId);
        
        // Update UI based on current state
        if (this.gameState === 'WAITING_FOR_PLAYERS') {
            this.showLobby();
        } else if (this.gameState === 'WAITING_FOR_BETS') {
            this.showBettingInterface();
        } else if (this.gameState === 'IN_PROGRESS') {
            this.showGameInterface();
        } else if (this.gameState === 'COMPLETED') {
            this.handleGameEnded({
                winner: data.status.winner,
                pot: data.status.pot
            });
        }
        
        this.updatePlayersList();
        this.updateBetsDisplay();
        this.updateGameStatus();
    }
    
    handleError(data) {
        this.showError(data.message);
    }
    
    animateShot(angle, power, result) {
        // Simplified animation - in a real game, you would implement proper physics
        const cueBall = document.getElementById('cue-ball');
        
        // Calculate movement based on angle and power
        const distance = power * 200; // Scale power to pixels
        const dx = Math.cos(angle) * distance;
        const dy = Math.sin(angle) * distance;
        
        // Animate cue ball
        cueBall.style.transition = 'transform 0.5s ease-out';
        cueBall.style.transform = `translate(${dx}px, ${dy}px)`;
        
        // Reset after animation
        setTimeout(() => {
            cueBall.style.transition = '';
            cueBall.style.transform = '';
        }, 500);
    }
    
    updatePlayersList() {
        const playersList = document.getElementById('players-list');
        playersList.innerHTML = '';
        
        this.players.forEach(player => {
            const li = document.createElement('li');
            li.textContent = player.name;
            if (player.id === this.playerId) {
                li.classList.add('me');
            }
            playersList.appendChild(li);
        });
    }
    
    updateBetsDisplay() {
        const betsList = document.getElementById('bets-list');
        betsList.innerHTML = '';
        
        for (const playerId in this.bets) {
            const player = this.players.find(p => p.id === playerId);
            if (player) {
                const li = document.createElement('li');
                li.textContent = `${player.name}: ${this.bets[playerId]} Stars`;
                betsList.appendChild(li);
            }
        }
        
        document.getElementById('pot-amount').textContent = this.pot;
    }
    
    updateGameStatus() {
        const statusElement = document.getElementById('game-status');
        
        if (this.gameState === 'WAITING_FOR_PLAYERS') {
            statusElement.textContent = `Waiting for players (${this.players.length}/${this.maxPlayers})`;
        } else if (this.gameState === 'WAITING_FOR_BETS') {
            statusElement.textContent = 'Waiting for bets';
        } else if (this.gameState === 'IN_PROGRESS') {
            const currentPlayer = this.players[this.currentPlayerIndex];
            statusElement.textContent = `Current turn: ${currentPlayer.name}`;
            
            // Highlight current player
            document.querySelectorAll('#players-list li').forEach((li, index) => {
                if (index === this.currentPlayerIndex) {
                    li.classList.add('current');
                } else {
                    li.classList.remove('current');
                }
            });
        } else if (this.gameState === 'COMPLETED') {
            statusElement.textContent = 'Game completed';
        }
        
        // Update turn indicator
        if (this.isMyTurn) {
            document.getElementById('turn-indicator').style.display = 'block';
        } else {
            document.getElementById('turn-indicator').style.display = 'none';
        }
    }
    
    addChatMessage(playerId, message, timestamp) {
        const chatMessages = document.getElementById('chat-messages');
        const player = this.players.find(p => p.id === playerId);
        const playerName = player ? player.name : 'Unknown';
        
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message');
        if (playerId === this.playerId) {
            messageElement.classList.add('me');
        }
        
        const time = new Date(timestamp).toLocaleTimeString();
        messageElement.innerHTML = `
            <span class="player-name">${playerName}</span>
            <span class="message-time">${time}</span>
            <div class="message-text">${message}</div>
        `;
        
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    showMainMenu() {
        document.getElementById('main-menu').style.display = 'block';
        document.getElementById('lobby').style.display = 'none';
        document.getElementById('game-interface').style.display = 'none';
        
        // Reset game state
        this.gameId = null;
        this.gameState = 'waiting';
        this.players = [];
        this.bets = {};
        this.pot = 0;
    }
    
    showLobby() {
        document.getElementById('main-menu').style.display = 'none';
        document.getElementById('lobby').style.display = 'block';
        document.getElementById('game-interface').style.display = 'none';
        
        this.updatePlayersList();
    }
    
    showBettingInterface() {
        document.getElementById('betting-interface').style.display = 'block';
    }
    
    showGameInterface() {
        document.getElementById('main-menu').style.display = 'none';
        document.getElementById('lobby').style.display = 'none';
        document.getElementById('game-interface').style.display = 'block';
    }
    
    showJoinGameDialog() {
        document.getElementById('join-game-dialog').style.display = 'block';
    }
    
    hideJoinGameDialog() {
        document.getElementById('join-game-dialog').style.display = 'none';
    }
    
    showError(message) {
        // Show error message in UI
        const errorElement = document.getElementById('error-message');
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        // Hide after 3 seconds
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 3000);
    }
}

// Initialize the game when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.poolGame = new PoolGame();
});