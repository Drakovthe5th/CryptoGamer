class TONopolyGame {
    constructor() {
        this.telegramApp = window.Telegram.WebApp;
        this.telegramApp.expand();
        this.telegramApp.enableClosingConfirmation();
        
        this.gameState = null;
        this.playerColor = null;
        this.socket = null;
        this.gameId = this.getGameIdFromUrl() || this.generateGameId();
        
        this.init();
    }
    
    async init() {
        // Initialize UI
        this.renderLobby();
        this.setupEventListeners();
        
        // Update URL with game ID if not present
        if (!this.getGameIdFromUrl()) {
            this.updateUrlWithGameId();
        }
        
        // Connect to WebSocket
        await this.connectWebSocket();
        
        // Load user data
        await this.loadUserData();
        
        // Join the game
        await this.joinGame();
    }
    
    generateGameId() {
        return 'game_' + Math.random().toString(36).substr(2, 9);
    }
    
    getGameIdFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('game_id');
    }
    
    updateUrlWithGameId() {
        const newUrl = window.location.origin + window.location.pathname + 
                      '?game_id=' + this.gameId;
        window.history.replaceState({}, '', newUrl);
        document.getElementById('game-id').textContent = 'Game: ' + this.gameId;
    }
    
    async connectWebSocket() {
        const user = this.telegramApp.initDataUnsafe.user;
        const wsUrl = `wss://yourdomain.com/ws/tonopoly/${this.gameId}/${user.id}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleGameUpdate(data);
        };
        
        this.socket.onopen = () => {
            console.log('Connected to TONopoly game server');
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showMessage('Connection error. Please refresh the page.', 'error');
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket connection closed');
        };
    }
    
    async joinGame() {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'join',
            user_id: user.id,
            username: user.username || user.first_name,
            color: this.playerColor
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    async setBet(amount) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'set_bet',
            user_id: user.id,
            game_id: this.gameId,
            amount: parseInt(amount)
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    async rollDice() {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'roll_dice',
            user_id: user.id,
            game_id: this.gameId
        };
        
        document.getElementById('roll-btn').disabled = true;
        this.socket.send(JSON.stringify(request));
    }
    
    async movePiece(pieceIndex) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'move_piece',
            user_id: user.id,
            game_id: this.gameId,
            piece_index: pieceIndex
        };
        
        this.socket.send(JSON.stringify(request));
        this.hidePieceSelection();
    }
    
    async stakeCoins(amount) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'stake_coins',
            user_id: user.id,
            game_id: this.gameId,
            amount: parseInt(amount)
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    handleGameUpdate(data) {
        switch (data.type) {
            case 'game_state':
                this.gameState = data.game_state;
                this.updateGameUI();
                break;
                
            case 'player_joined':
                this.showMessage(`${data.username} joined the game`, 'info');
                this.updatePlayersList();
                break;
                
            case 'player_left':
                this.showMessage('A player left the game', 'info');
                this.updatePlayersList();
                break;
                
            case 'bet_set':
                this.showMessage(`Bet set to ${data.amount} Telegram Stars`, 'info');
                this.updateBetUI(data.amount);
                break;
                
            case 'bet_invoice':
                this.showBetInvoice(data.invoice_url, data.amount);
                break;
                
            case 'dice_rolled':
                this.showMessage(`${this.getPlayerName(data.user_id)} rolled a ${data.dice_value}`, 'info');
                this.updateDice(data.dice_value);
                
                if (data.user_id === this.telegramApp.initDataUnsafe.user.id) {
                    this.showPieceSelection();
                }
                break;
                
            case 'piece_moved':
                this.showMessage(data.message, 'info');
                this.updateBoard();
                break;
                
            case 'coins_staked':
                this.showMessage(`${this.getPlayerName(data.user_id)} staked ${data.amount} coins`, 'info');
                this.updateGameUI();
                break;
                
            case 'game_over':
                this.showGameOver(data.winner, data.winnings);
                break;
                
            case 'error':
                this.showMessage(data.message, 'error');
                break;
        }
    }
    
    updateGameUI() {
        if (!this.gameState) return;
        
        // Update game status
        document.getElementById('game-status').textContent = 
            this.getGameStateName(this.gameState.state);
        
        // Update players list
        this.updatePlayersList();
        
        // Update board
        this.updateBoard();
        
        // Update turn indicator
        this.updateTurnIndicator();
        
        // Show appropriate screen based on game state
        this.showScreenForState();
    }
    
    showScreenForState() {
        const screens = ['lobby', 'game', 'game-over'];
        screens.forEach(screen => {
            document.getElementById(screen).classList.remove('active');
        });
        
        switch (this.gameState.state) {
            case 0: // LOBBY
                document.getElementById('lobby').classList.add('active');
                break;
            case 1: // WAITING_FOR_BET
                document.getElementById('lobby').classList.add('active');
                break;
            case 2: // PLAYING
                document.getElementById('game').classList.add('active');
                break;
            case 3: // FINISHED
                document.getElementById('game-over').classList.add('active');
                break;
        }
    }
    
    updatePlayersList() {
        if (!this.gameState) return;
        
        const lobbyList = document.getElementById('players-list');
        const gameList = document.getElementById('game-players-list');
        
        lobbyList.innerHTML = '';
        gameList.innerHTML = '';
        
        this.gameState.players.forEach((player, index) => {
            const playerItem = document.createElement('div');
            playerItem.className = 'player-item';
            playerItem.innerHTML = `
                <div class="color-indicator" style="background: ${player.color};"></div>
                <span class="player-name">${player.username}</span>
                ${player.has_paid_bet ? '<span class="bet-status">✓</span>' : ''}
                ${index === this.gameState.current_turn_index ? '<span class="turn-indicator">🎲</span>' : ''}
            `;
            
            lobbyList.appendChild(playerItem.cloneNode(true));
            gameList.appendChild(playerItem);
        });
    }
    
    updateBoard() {
        if (!this.gameState) return;
        
        const board = document.getElementById('tonopoly-board');
        board.innerHTML = '';
        
        // Render board spaces
        this.gameState.board.forEach(space => {
            const spaceEl = document.createElement('div');
            spaceEl.className = `board-space ${space.type}`;
            spaceEl.style.left = this.calculateSpacePosition(space.position).x + 'px';
            spaceEl.style.top = this.calculateSpacePosition(space.position).y + 'px';
            spaceEl.title = space.name;
            
            // Add space number for debugging
            const numberEl = document.createElement('div');
            numberEl.className = 'space-number';
            numberEl.textContent = space.position;
            spaceEl.appendChild(numberEl);
            
            board.appendChild(spaceEl);
        });
        
        // Render player pieces
        this.gameState.players.forEach(player => {
            player.pieces.forEach((position, index) => {
                if (position > 0) {
                    const pieceEl = document.createElement('div');
                    pieceEl.className = `piece ${this.getColorClass(player.color)}`;
                    pieceEl.id = `piece-${player.user_id}-${index}`;
                    pieceEl.style.left = this.calculatePiecePosition(position, player.color).x + 'px';
                    pieceEl.style.top = this.calculatePiecePosition(position, player.color).y + 'px';
                    board.appendChild(pieceEl);
                }
            });
        });
    }
    
    calculateSpacePosition(position) {
        // Simplified calculation - would need proper algorithm for circular board
        const boardSize = 500; // Assuming fixed size for calculation
        const radius = boardSize / 2 - 20;
        const angle = (position / 52) * 2 * Math.PI;
        
        return {
            x: radius + radius * Math.cos(angle),
            y: radius + radius * Math.sin(angle)
        };
    }
    
    calculatePiecePosition(position, color) {
        // This would need a more sophisticated algorithm based on board layout
        // For now, using the same as space position
        return this.calculateSpacePosition(position);
    }
    
    getColorClass(color) {
        const colorMap = {
            '#F7931A': 'bitcoin',
            '#627EEA': 'ethereum',
            '#0088CC': 'ton',
            '#27AE60': 'stablecoin'
        };
        
        return colorMap[color] || 'bitcoin';
    }
    
    updateTurnIndicator() {
        if (!this.gameState || this.gameState.players.length === 0) return;
        
        const currentPlayer = this.gameState.players[this.gameState.current_turn_index];
        document.getElementById('current-player').textContent = currentPlayer.username;
        
        // Enable roll button if it's current player's turn
        const currentUser = this.telegramApp.initDataUnsafe.user;
        document.getElementById('roll-btn').disabled = 
            currentPlayer.user_id !== currentUser.id;
    }
    
    updateDice(value) {
        document.getElementById('dice').textContent = value;
    }
    
    updateBetUI(amount) {
        document.getElementById('bet-amount').value = amount;
        
        // Enable start game button if user is creator and all players have joined
        const user = this.telegramApp.initDataUnsafe.user;
        if (this.gameState && user.id === this.gameState.creator_id) {
            document.getElementById('start-game').disabled = 
                this.gameState.players.length < 2;
        }
    }
    
    showPieceSelection() {
        const pieceSelection = document.getElementById('piece-selection');
        pieceSelection.style.display = 'block';
        
        // Highlight available pieces (those that can move)
        const pieceOptions = document.querySelectorAll('.piece-option');
        pieceOptions.forEach((option, index) => {
            const currentUser = this.telegramApp.initDataUnsafe.user;
            const player = this.gameState.players.find(p => p.user_id === currentUser.id);
            
            if (player) {
                const canMove = this.canPieceMove(player, index);
                option.classList.toggle('available', canMove);
                option.style.backgroundColor = player.color;
                option.onclick = canMove ? () => this.movePiece(index) : null;
            }
        });
    }
    
    hidePieceSelection() {
        document.getElementById('piece-selection').style.display = 'none';
    }
    
    canPieceMove(player, pieceIndex) {
        const position = player.pieces[pieceIndex];
        const diceValue = this.gameState.dice_value;
        
        // Piece at home needs a 6 to move
        if (position === 0 && diceValue === 6) {
            return true;
        }
        
        // Piece not at home can always move if it won't overshoot
        if (position > 0 && position + diceValue <= 57) {
            return true;
        }
        
        return false;
    }
    
    showBetInvoice(invoiceUrl, amount) {
        document.getElementById('bet-modal-amount').textContent = amount;
        const modal = document.getElementById('bet-modal');
        modal.classList.add('active');
        
        document.getElementById('pay-bet').onclick = () => {
            this.telegramApp.openInvoice(invoiceUrl, (status) => {
                modal.classList.remove('active');
                if (status === 'paid') {
                    this.showMessage('Bet payment successful!', 'success');
                } else {
                    this.showMessage('Bet payment cancelled', 'error');
                }
            });
        };
        
        document.getElementById('cancel-bet').onclick = () => {
            modal.classList.remove('active');
            this.showMessage('Bet payment cancelled', 'error');
        };
    }
    
    showGameOver(winnerId, winnings) {
        const winner = this.gameState.players.find(p => p.user_id === winnerId);
        if (winner) {
            document.getElementById('winner-name').textContent = winner.username;
            document.getElementById('winnings-amount').textContent = winnings;
        }
    }
    
    showMessage(message, type = 'info') {
        const messagesContainer = document.getElementById('game-messages');
        const messageEl = document.createElement('div');
        messageEl.className = `message ${type}`;
        messageEl.textContent = message;
        
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.parentNode.removeChild(messageEl);
            }
        }, 5000);
    }
    
    getPlayerName(userId) {
        const player = this.gameState.players.find(p => p.user_id === userId);
        return player ? player.username : 'Unknown';
    }
    
    getGameStateName(state) {
        const states = ['Lobby', 'Waiting for bets', 'Playing', 'Finished'];
        return states[state] || 'Unknown';
    }
    
    renderLobby() {
        // Initial lobby rendering
        document.getElementById('lobby').classList.add('active');
    }
    
    setupEventListeners() {
        // Color selection
        document.querySelectorAll('.color-option').forEach(option => {
            option.addEventListener('click', () => {
                document.querySelectorAll('.color-option').forEach(o => {
                    o.classList.remove('selected');
                });
                option.classList.add('selected');
                this.playerColor = option.getAttribute('data-color');
            });
        });
        
        // Set bet button
        document.getElementById('set-bet').addEventListener('click', () => {
            const amount = document.getElementById('bet-amount').value;
            if (amount > 0) {
                this.setBet(amount);
            } else {
                this.showMessage('Please enter a valid bet amount', 'error');
            }
        });
        
        // Start game button
        document.getElementById('start-game').addEventListener('click', () => {
            // This would send a start game request to the server
            this.showMessage('Game starting...', 'info');
        });
        
        // Roll dice button
        document.getElementById('roll-btn').addEventListener('click', () => {
            this.rollDice();
        });
        
        // Invite friends button
        document.getElementById('invite-friends').addEventListener('click', () => {
            this.inviteFriends();
        });
        
        // Game over buttons
        document.getElementById('play-again').addEventListener('click', () => {
            location.reload();
        });
        
        document.getElementById('back-to-lobby').addEventListener('click', () => {
            window.location.href = '/games';
        });
        
        document.getElementById('share-result').addEventListener('click', () => {
            this.shareResult();
        });
    }
    
    async loadUserData() {
        try {
            // This would fetch user data from your backend
            const user = this.telegramApp.initDataUnsafe.user;
            document.getElementById('username').textContent = user.username || user.first_name;
            
            // Example balance - would come from your backend
            document.getElementById('balance').textContent = '15000 gc';
            
        } catch (error) {
            console.error('Failed to load user data:', error);
        }
    }
    
    inviteFriends() {
        const shareUrl = `https://t.me/YourBotName?start=tonopoly_${this.gameId}`;
        this.telegramApp.showPopup({
            title: 'Invite Friends',
            message: `Invite friends to play TONopoly! Share this link: ${shareUrl}`,
            buttons: [{ type: 'ok' }]
        });
    }
    
    shareResult() {
        if (!this.gameState || !this.gameState.winner) return;
        
        const winner = this.gameState.players.find(p => p.user_id === this.gameState.winner);
        const message = `I just played TONopoly and ${winner.username} won ${this.gameState.total_pot * 0.95} Telegram Stars!`;
        
        this.telegramApp.shareMessage(message);
    }
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    new TONopolyGame();
});